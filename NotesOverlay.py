# -----------------------------------------------------------------------------
# SnapReview - OpenRV Review Notes Plugin
# -----------------------------------------------------------------------------
# Adds a "SnapReview > Add Note" menu to OpenRV for adding text annotations
# to frames. Notes are rendered as white text with a black outline overlay.
#
# Notes are stored in RVPaint node properties and persist in session files
# (including autosave), so they survive crashes and session reloads.
#
# ARCHITECTURE:
# - NotesOverlay.py: Main Python plugin (MinorMode)
# - notes_dialog.mu: Custom Qt dialog for text input (Mu module)
#
# The Mu module is required because:
# 1. RV's native text entry mode doesn't support copy/paste
# 2. PySide2/6 may not be available in all RV builds
# 3. Mu provides direct access to Qt widgets via RV's Qt bindings
#
# KEY TECHNICAL DISCOVERIES:
# - QPushButton.clicked signal passes (bool checked) to callbacks
# - Mu closures don't work; use module-level globals for widget refs
# - QLabel requires (text, parent, flags) constructor signature
# - Use sendInternalEvent() for Mu-to-Python communication
# -----------------------------------------------------------------------------

import traceback

# -----------------------------------------------------------------------------
# RV Imports
# -----------------------------------------------------------------------------
from rv import commands, extra_commands
from rv.rvtypes import MinorMode

# -----------------------------------------------------------------------------
# RV Runtime for Mu integration
# -----------------------------------------------------------------------------
import rv.runtime

# -----------------------------------------------------------------------------
# PySide imports (optional, for improved text input)
# -----------------------------------------------------------------------------
PYSIDE_AVAILABLE = False
PYSIDE_VERSION = None

try:
    from PySide2.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QPushButton, QLabel
    from PySide2.QtCore import Qt
    import rv.qtutils
    PYSIDE_AVAILABLE = True
    PYSIDE_VERSION = "PySide2"
except ImportError:
    try:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QPushButton, QLabel
        from PySide6.QtCore import Qt
        import rv.qtutils
        PYSIDE_AVAILABLE = True
        PYSIDE_VERSION = "PySide6"
    except ImportError:
        pass

# PySide not required - using QInputDialog via Mu instead


class NotesOverlayMode(MinorMode):
    """
    MinorMode that provides note overlay functionality for OpenRV.

    Features:
    - SnapReview > Add Note menu item (shift+n hotkey)
    - Native RV text entry mode for input (Mu-based)
    - White text with black outline rendered on current frame
    - Notes stored in RVPaint node (persists in session/autosave)
    """

    def __init__(self):
        """Initialize the NotesOverlay mode."""
        MinorMode.__init__(self)

        # Track frame when note dialog was opened
        self._pending_note_frame = None

        # Initialize mode with menu and keybindings
        self.init(
            "notes-overlay-mode",  # Mode name
            # Global key bindings: (event, callback, description)
            [
                ("key-down--N", self.open_note_dialog, "Add note to current frame"),
                # Ctrl+Shift+C (Windows/Linux) and Cmd+Shift+C (macOS)
                ("key-down--control--C", self.copy_notes_to_clipboard, "Copy notes to clipboard"),
                ("key-down--meta--C", self.copy_notes_to_clipboard, "Copy notes to clipboard"),
                # Ctrl+Shift+S (Windows/Linux) and Cmd+Shift+S (macOS)
                ("key-down--control--S", self.save_review, "Save review to folder"),
                ("key-down--meta--S", self.save_review, "Save review to folder"),
                # Internal event for receiving text from Mu dialog
                ("notes-overlay-text-entered", self._on_text_entered, "Handle entered note text"),
            ],
            None,  # No override bindings
            # Menu structure: (menu_name, [(item_name, callback, hotkey, state_hook), ...])
            [
                ("SnapReview", [
                    ("Add Note", self.open_note_dialog, "N", None),
                    ("Copy Notes", self.copy_notes_to_clipboard, "C", None),
                    ("Save Review", self.save_review, "S", None),
                ]),
            ],
        )

    # -------------------------------------------------------------------------
    # Menu/Dialog Methods
    # -------------------------------------------------------------------------

    def open_note_dialog(self, event):
        """
        Show custom multi-line note dialog with copy/paste support.

        Uses a custom Mu module (notes_dialog.mu) that creates a Qt dialog
        with QTextEdit for proper multi-line text input. This approach was
        chosen because:
        - RV's native text entry mode doesn't support copy/paste
        - PySide2/6 is not available in this RV build
        - Mu's Qt bindings provide full Qt widget access

        The dialog sends text back via sendInternalEvent(), which is
        received by _on_text_entered().

        Technical notes:
        - 'require notes_dialog' loads the .mu file from RV's Mu path
        - The Mu module uses global variables for Qt widget references
          (closures don't work in Mu callbacks)
        - QPushButton.clicked callbacks must accept (bool checked) parameter
        """
        # Check if there's a source at the current frame
        current_frame = commands.frame()
        sources = commands.sourcesAtFrame(current_frame)
        if not sources:
            extra_commands.displayFeedback("No source at frame - cannot add note", 2.0)
            return

        self._pending_note_frame = current_frame

        try:
            # Load and call the custom Mu dialog module
            rv.runtime.eval("require notes_dialog; notes_dialog.showNoteDialog();", [])
        except Exception as e:
            extra_commands.displayFeedback(f"Note dialog failed: {e}", 3.0)
            print(f"NotesOverlay: Dialog error - {e}")

    def _open_note_dialog_legacy(self, event):
        """
        Legacy: Open note input using RV's native text entry mode.

        This is the old method that uses RV's built-in startTextEntryMode.
        Kept as fallback but not used by default because:
        - No copy/paste support
        - Single line only
        - Easy to accidentally close and lose input
        """
        self._pending_note_frame = commands.frame()

        try:
            mu_code = 'rvui.startTextEntryMode(\\: (string;) { "Enter note: "; }, \\: (void; string t) { commands.sendInternalEvent("notes-overlay-text-entered", t, ""); }, false)(nil);'
            rv.runtime.eval(mu_code, [])
            extra_commands.displayFeedback("Type note and press Enter...", 2.0)
        except Exception:
            extra_commands.displayFeedback("Error starting text entry - see console", 2.0)
            print(traceback.format_exc())

    def _on_text_entered(self, event):
        """
        Handle the internal event when text is entered via note dialog.

        Args:
            event: The internal event containing the entered text.
        """
        try:
            note_text = event.contents().strip()

            if note_text:
                # Use the frame from when dialog was opened
                frame = getattr(self, '_pending_note_frame', commands.frame())
                self._add_note_to_frame(note_text, frame)
                extra_commands.displayFeedback("Note added", 1.5)
            else:
                extra_commands.displayFeedback("Empty note - cancelled", 1.0)

        except Exception:
            extra_commands.displayFeedback("Error adding note - see console", 2.0)
            print(traceback.format_exc())

    def _add_note_to_frame(self, note_text, frame):
        """
        Add a note to a specific frame.

        Args:
            note_text: The text content of the note.
            frame: The global timeline frame number.
        """
        # Get the source at the current frame
        sources = commands.sourcesAtFrame(frame)

        if not sources:
            extra_commands.displayFeedback("No source at frame", 2.0)
            return

        # Use the first source
        source = sources[0]

        # Convert global timeline frame to source-relative frame
        # This is critical for sequences where source frames != timeline frames
        try:
            source_frame = extra_commands.sourceFrame(frame)
        except Exception as e:
            extra_commands.displayFeedback("Cannot add note - frame conversion failed", 2.0)
            print(f"NotesOverlay: sourceFrame conversion failed for frame {frame}: {e}")
            return

        source_group = commands.nodeGroup(source)
        paint_nodes = extra_commands.nodesInGroupOfType(source_group, "RVPaint")

        if not paint_nodes:
            extra_commands.displayFeedback("No paint node found", 2.0)
            return

        paint_node = paint_nodes[0]

        # Format note as bullet point (preserve original text exactly)
        if note_text:
            formatted_note = "- " + note_text
        else:
            return

        # Wrap long lines
        wrapped_note = self.wrap_text(formatted_note)

        # Count existing notes for stacking offset
        existing_notes = self.count_note_lines(source_frame)

        # Draw the note with outline
        self._draw_note_with_outline_on_frame(paint_node, source_frame, wrapped_note, existing_notes, source)

        # Mark the frame on the timeline so user can see which frames have notes
        commands.markFrame(frame, True)

        # Force redraw
        commands.redraw()

    def _draw_note_with_outline_on_frame(self, paint_node, frame, text, line_offset, source=None):
        """
        Draw note text with black outline effect on a specific frame.

        Creates 4 shadow texts at offset positions (black) and one main text (white)
        to create an outline effect for readability.

        Args:
            paint_node: The RVPaint node to draw on.
            frame: The source-relative frame number for drawing.
            text: Note text to display.
            line_offset: Vertical offset based on existing notes (in lines).
            source: The source node to get dimensions from (avoids frame lookup issues).
        """
        scale = self.get_image_scale(source=source)

        # Get image dimensions from source media info
        try:
            if source:
                info = commands.sourceMediaInfo(source)
            else:
                # Fallback to current frame lookup (less reliable for sequences)
                sources = commands.sourcesAtFrame(commands.frame())
                info = commands.sourceMediaInfo(sources[0]) if sources else {}
            img_w = info.get("width", 1920)
            img_h = info.get("height", 1080)
            aspect = img_w / img_h
        except Exception:
            aspect = 16 / 9

        # RV paint coordinates:
        # x: -aspect/2 (left) to +aspect/2 (right)
        # y: -0.5 (bottom) to +0.5 (top)
        left_edge = -aspect / 2
        top_edge = 0.5

        # Padding from edges
        padding_x = 0.06  # ~6% from left edge
        padding_y = 0.15  # 15% down from top

        # Line spacing from constant
        line_spacing = self.LINE_SPACING

        pos_x = left_edge + padding_x
        pos_y = top_edge - padding_y - (line_offset * line_spacing)

        # Shadow offsets for outline effect (4 corners + 4 cardinals for thicker outline)
        # Offset proportional to text size
        shadow_offset = 0.003  # 1.5x outline for readability over white
        offsets = [
            # 4 corners
            (-shadow_offset, -shadow_offset),
            (+shadow_offset, -shadow_offset),
            (+shadow_offset, +shadow_offset),
            (-shadow_offset, +shadow_offset),
            # 4 cardinal directions for thicker outline
            (0, -shadow_offset),
            (0, +shadow_offset),
            (-shadow_offset, 0),
            (+shadow_offset, 0),
        ]

        # Draw black shadows first (behind)
        for i, (ox, oy) in enumerate(offsets):
            shadow_pos = [pos_x + ox, pos_y + oy]
            self._draw_text_on_node(paint_node, f"shadow{i}", frame, text, self.BLACK, shadow_pos, scale)

        # Draw white text on top
        self._draw_text_on_node(paint_node, "note", frame, text, self.WHITE, [pos_x, pos_y], scale)

    def _draw_text_on_node(self, paint_node, label, frame, text, color, position, scale):
        """
        Draw text on a specific paint node.

        Follows RV's paint property conventions for text rendering.
        Creates all properties that RV's annotation mode uses.

        Args:
            paint_node: The RVPaint node name.
            label: Label for the text property.
            frame: Frame number.
            text: Text content.
            color: RGBA color list.
            position: [x, y] position.
            scale: Text scale factor.
        """
        try:
            # Get unique ID and increment
            paint_prop = f"{paint_node}.paint"
            unique_id = commands.getIntProperty(f"{paint_prop}.nextId")[0]
            commands.setIntProperty(f"{paint_prop}.nextId", [unique_id + 1], True)

            # Build property names (format: node.text:id:frame:label)
            text_name = f"text:{unique_id}:{frame}:{label}"
            text_prop = f"{paint_node}.{text_name}"

            # Ensure paint layer is visible
            commands.setIntProperty(f"{paint_prop}.show", [1])

            # Create ALL properties that RV's annotation mode creates
            commands.newProperty(f"{text_prop}.position", commands.FloatType, 2)
            commands.newProperty(f"{text_prop}.color", commands.FloatType, 4)
            commands.newProperty(f"{text_prop}.spacing", commands.FloatType, 1)
            commands.newProperty(f"{text_prop}.size", commands.FloatType, 1)
            commands.newProperty(f"{text_prop}.scale", commands.FloatType, 1)
            commands.newProperty(f"{text_prop}.rotation", commands.FloatType, 1)
            commands.newProperty(f"{text_prop}.font", commands.StringType, 1)
            commands.newProperty(f"{text_prop}.text", commands.StringType, 1)
            commands.newProperty(f"{text_prop}.origin", commands.StringType, 1)
            commands.newProperty(f"{text_prop}.debug", commands.IntType, 1)
            commands.newProperty(f"{text_prop}.startFrame", commands.IntType, 1)
            commands.newProperty(f"{text_prop}.duration", commands.IntType, 1)
            commands.newProperty(f"{text_prop}.mode", commands.IntType, 1)

            # Set property values (matching RV's annotation mode defaults)
            commands.setFloatProperty(f"{text_prop}.position", position, True)
            commands.setFloatProperty(f"{text_prop}.color", color, True)
            commands.setFloatProperty(f"{text_prop}.size", [self.TEXT_SIZE], True)
            commands.setFloatProperty(f"{text_prop}.scale", [1.0], True)  # Use fixed scale
            commands.setFloatProperty(f"{text_prop}.spacing", [0.8], True)
            commands.setFloatProperty(f"{text_prop}.rotation", [0.0], True)
            commands.setStringProperty(f"{text_prop}.font", [""], True)
            commands.setStringProperty(f"{text_prop}.text", [text], True)
            commands.setStringProperty(f"{text_prop}.origin", [""], True)
            commands.setIntProperty(f"{text_prop}.debug", [0], True)
            commands.setIntProperty(f"{text_prop}.startFrame", [frame], True)
            commands.setIntProperty(f"{text_prop}.duration", [1], True)
            commands.setIntProperty(f"{text_prop}.mode", [0], True)  # RenderOverMode = 0

            # Create frame order property
            order_prop = f"{paint_node}.frame:{frame}.order"
            if not commands.propertyExists(order_prop):
                commands.newProperty(order_prop, commands.StringType, 1)

            # Append to order list
            commands.insertStringProperty(order_prop, [text_name])

        except Exception as e:
            print(f"NotesOverlay: Error creating text element: {e}")

    # -------------------------------------------------------------------------
    # RVPaint Node Helpers
    # -------------------------------------------------------------------------

    def get_source_paint_node(self):
        """
        Get the RVPaint node for the current source at the current frame.

        Returns:
            str: The RVPaint node name, or None if no source at current frame.
        """
        view_frame = commands.frame()
        sources = commands.sourcesAtFrame(view_frame)

        if not sources:
            return None

        source = sources[0]
        source_group = commands.nodeGroup(source)
        paint_nodes = extra_commands.nodesInGroupOfType(source_group, "RVPaint")

        if paint_nodes:
            return paint_nodes[0]
        return None

    def get_notes_from_paint(self, frame):
        """
        Read existing notes from RVPaint for a specific frame.

        Scans the paint node properties for text entries labeled with ':note:'
        and returns the list of note texts on that frame.

        Args:
            frame: The frame number to get notes for.

        Returns:
            list: List of note text strings on that frame.
        """
        paint_node = self.get_source_paint_node()
        if not paint_node:
            return []

        notes = []

        try:
            # Get all properties on the paint node
            properties = commands.properties(paint_node)

            # Look for frame order properties (e.g., "node.frame:123.order")
            for prop in properties:
                if ".order" in prop and f"frame:{frame}" in prop:
                    # Get the order list for this frame
                    order_data = commands.getStringProperty(prop)

                    for element in order_data:
                        # Find note text entries (labeled with ':note:')
                        if ":note:" in element:
                            text_prop = f"{paint_node}.{element}.text"
                            if commands.propertyExists(text_prop):
                                note_text = commands.getStringProperty(text_prop)[0]
                                notes.append(note_text)

        except Exception:
            # If any error reading properties, return empty list
            print(traceback.format_exc())

        return notes

    def count_note_lines(self, frame):
        """
        Count total lines from all notes on a frame for stacking offset.

        Counts actual text lines including wrapped lines, not just note count.

        Args:
            frame: The frame number.

        Returns:
            int: Total number of lines from all notes on this frame.
        """
        paint_node = self.get_source_paint_node()
        if not paint_node:
            return 0

        total_lines = 0

        try:
            order_prop = f"{paint_node}.frame:{frame}.order"
            if commands.propertyExists(order_prop):
                order_data = commands.getStringProperty(order_prop)
                # Find note text entries (not shadows)
                for element in order_data:
                    if element.endswith(":note"):
                        # Read the actual text to count lines
                        text_prop = f"{paint_node}.{element}.text"
                        if commands.propertyExists(text_prop):
                            note_text = commands.getStringProperty(text_prop)[0]
                            # Count lines (newlines + 1)
                            total_lines += note_text.count("\n") + 1
        except Exception:
            pass

        return total_lines

    # -------------------------------------------------------------------------
    # Text Utilities
    # -------------------------------------------------------------------------

    def wrap_text(self, text, max_length=None):
        """
        Wrap text to a maximum line length.

        Preserves existing line breaks from user input.
        Forces breaks on long words using shorter limit (for wide chars).
        Keeps bullet point prefix attached to first word.

        Args:
            text: The text to wrap.
            max_length: Maximum characters per line (uses class constant if None).

        Returns:
            str: Text with line breaks inserted for wrapping.
        """
        if max_length is None:
            max_length = self.MAX_CHARS_PER_LINE

        # Shorter limit for force-breaking single words (may have wide chars)
        force_break_length = self.FORCE_BREAK_LENGTH

        # Split by existing newlines first
        input_lines = text.split("\n")
        wrapped_lines = []

        for line in input_lines:
            if len(line) <= max_length:
                wrapped_lines.append(line)
            else:
                # Word-wrap this line
                words = line.split()

                # If first word is just "-", merge it with second word
                if len(words) >= 2 and words[0] == "-":
                    words = ["- " + words[1]] + words[2:]

                # Handle case where there's only one (possibly merged) word
                if len(words) == 1:
                    # Force break using shorter limit for wide chars
                    long_word = words[0]
                    while len(long_word) > force_break_length:
                        wrapped_lines.append(long_word[:force_break_length])
                        long_word = long_word[force_break_length:]
                    if long_word:
                        wrapped_lines.append(long_word)
                else:
                    current_line = ""
                    for word in words:
                        # If word itself is too long, break it with shorter limit
                        if len(word) > force_break_length:
                            if current_line:
                                wrapped_lines.append(current_line)
                                current_line = ""
                            while len(word) > force_break_length:
                                wrapped_lines.append(word[:force_break_length])
                                word = word[force_break_length:]
                            if word:
                                current_line = word
                        elif len(current_line) + len(word) + 1 <= max_length:
                            if current_line:
                                current_line += " " + word
                            else:
                                current_line = word
                        else:
                            if current_line:
                                wrapped_lines.append(current_line)
                            current_line = word

                    if current_line:
                        wrapped_lines.append(current_line)

        return "\n".join(wrapped_lines)

    # -------------------------------------------------------------------------
    # Text Rendering Constants
    # -------------------------------------------------------------------------

    # Text size (relative to image height, 0.005 = 0.5% of height)
    # Relationship: max_chars = 0.29 / TEXT_SIZE (+5% from 0.275)
    # At 0.005 → 58 chars, at 0.004 → 72 chars, at 0.006 → 48 chars
    TEXT_SIZE = 0.005

    # Calculated max characters per line (scales with text size)
    MAX_CHARS_PER_LINE = int(0.29 / TEXT_SIZE)  # 58 at default size
    FORCE_BREAK_LENGTH = int(MAX_CHARS_PER_LINE * 0.65)  # 37 at default size

    # Line spacing (relative to image height)
    LINE_SPACING = 0.08  # 8% between lines

    # Base scale for resolution normalization
    BASE_SCALE = 1.0
    REFERENCE_HEIGHT = 1080.0

    # Colors (RGBA)
    WHITE = [1.0, 1.0, 1.0, 1.0]
    BLACK = [0.0, 0.0, 0.0, 1.0]

    # Shadow offset for outline effect (in normalized coords)
    SHADOW_OFFSET = 0.003

    # -------------------------------------------------------------------------
    # Note Adding Methods
    # -------------------------------------------------------------------------

    def get_image_scale(self, frame=None, source=None):
        """
        Calculate text scale factor based on source image dimensions.

        Normalizes text size relative to a 1080p reference so text appears
        similarly sized regardless of source resolution.

        Args:
            frame: Optional timeline frame number to sample; defaults to current frame.
            source: Optional source node to get dimensions from (preferred over frame).

        Returns:
            float: Scale factor for text size.
        """
        try:
            if source:
                info = commands.sourceMediaInfo(source)
            else:
                if frame is None:
                    frame = commands.frame()
                sources = commands.sourcesAtFrame(frame)
                if not sources:
                    return self.BASE_SCALE
                info = commands.sourceMediaInfo(sources[0])

            image_height = info.get("height", self.REFERENCE_HEIGHT)
            return self.BASE_SCALE * (self.REFERENCE_HEIGHT / image_height)
        except Exception:
            pass

        return self.BASE_SCALE

    def add_note(self, note_text):
        """
        Add a note to the current frame.

        Convenience method that calls _add_note_to_frame with current frame.

        Args:
            note_text: The text content of the note.
        """
        self._add_note_to_frame(note_text, commands.frame())

    # -------------------------------------------------------------------------
    # Save Review
    # -------------------------------------------------------------------------

    def save_review(self, event):
        """
        Save review to a folder with session, notes text file, and annotated frame JPGs.

        Creates a timestamped folder next to the source file containing:
        - RV session file (.rv)
        - Notes text file ({source}_review_notes.txt)
        - JPG exports of all annotated frames

        Also copies notes to clipboard (same as Copy Notes).

        Folder naming: {YYYY-MM-DD_HHMM}_{source_name}-review/
        """
        import os
        from datetime import datetime

        # ---------------------------------------------------------------------
        # Step 1: Get source info
        # ---------------------------------------------------------------------
        current_frame = commands.frame()
        sources = commands.sourcesAtFrame(current_frame)

        if not sources:
            extra_commands.displayFeedback("No source at current frame", 2.0)
            return

        source = sources[0]

        # Get source file path and name
        try:
            info = commands.sourceMediaInfo(source)
            source_path = info.get("file", "")
            if not source_path:
                extra_commands.displayFeedback("Cannot determine source file path", 2.0)
                return
        except Exception as e:
            extra_commands.displayFeedback(f"Error getting source info: {e}", 2.0)
            return

        # Extract source directory and base name (without extension)
        source_dir = os.path.dirname(source_path)
        source_filename = os.path.basename(source_path)
        source_name, _ = os.path.splitext(source_filename)

        # Strip image sequence frame range/padding patterns (e.g., .30-69@@@)
        source_name = self._strip_sequence_pattern(source_name)

        # Sanitize source name for filesystem (remove problematic characters)
        safe_source_name = self._sanitize_filename(source_name)

        # ---------------------------------------------------------------------
        # Step 2: Check for annotations (bail out early if none)
        # ---------------------------------------------------------------------
        # Temporarily switch to source view to check for annotations
        source_group = commands.nodeGroup(source)
        original_view = None
        has_annotations = False
        try:
            original_view = commands.viewNode()
            commands.setViewNode(source_group)
            rv.runtime.eval("require rvui; rvui.clearAllMarks(); rvui.markAnnotatedFrames();", [])
            marked_frames = commands.markedFrames()

            # Filter out frames with no visible content (empty text elements)
            # RV marks frames with any paint element, including empty ones
            paint_nodes = extra_commands.nodesInGroupOfType(source_group, "RVPaint")
            if paint_nodes and marked_frames:
                source_paint_node = paint_nodes[0]
                for frame in marked_frames:
                    texts, has_drawings = self.get_notes_for_frame(source_paint_node, frame)
                    # Filter blank texts using the same logic as normalize_note
                    valid_texts = [t for t in texts if self.normalize_note(t)]
                    if valid_texts or has_drawings:
                        has_annotations = True
                    else:
                        # Frame has only empty text elements - clean them up
                        self._clean_empty_paint_elements(source_paint_node, frame)

            # Re-mark after cleanup so timeline reflects accurate state
            if has_annotations:
                rv.runtime.eval("require rvui; rvui.clearAllMarks(); rvui.markAnnotatedFrames();", [])
        except Exception:
            has_annotations = False
        finally:
            if original_view:
                try:
                    commands.setViewNode(original_view)
                except Exception:
                    pass

        if not has_annotations:
            extra_commands.displayFeedback("No annotations found", 2.0)
            return

        # ---------------------------------------------------------------------
        # Step 3: Create review folder
        # ---------------------------------------------------------------------
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        folder_name = f"{timestamp}_{safe_source_name}-review"
        review_folder = os.path.join(source_dir, folder_name)

        try:
            os.makedirs(review_folder, exist_ok=True)
        except OSError as e:
            extra_commands.displayFeedback(f"Cannot create folder: {e}", 3.0)
            return

        # ---------------------------------------------------------------------
        # Step 3: Save session file
        # ---------------------------------------------------------------------
        session_filename = f"{safe_source_name}-review_session.rv"
        session_path = os.path.join(review_folder, session_filename)

        try:
            commands.saveSession(session_path, True, True)
        except Exception as e:
            extra_commands.displayFeedback(f"Error saving session: {e}", 3.0)
            print(f"NotesOverlay: Session save error - {e}")
            # Continue anyway - session save is not critical

        # ---------------------------------------------------------------------
        # Step 4: Create frames subfolder
        # ---------------------------------------------------------------------
        frames_folder = os.path.join(review_folder, "frames")
        try:
            os.makedirs(frames_folder, exist_ok=True)
        except OSError as e:
            print(f"NotesOverlay: Could not create frames folder - {e}")
            frames_folder = review_folder  # Fallback to main folder

        # ---------------------------------------------------------------------
        # Step 5: Gather notes and save (also copy to clipboard)
        # ---------------------------------------------------------------------
        # Pass review paths so they appear in the notes footer
        notes_text, total_notes, total_frames = self._gather_notes_for_export(
            source, frames_folder=frames_folder, session_path=session_path
        )

        if notes_text:
            # Save notes to file
            notes_filename = f"{safe_source_name}_review_notes.txt"
            notes_path = os.path.join(review_folder, notes_filename)
            try:
                with open(notes_path, "w", encoding="utf-8") as f:
                    f.write(notes_text)
            except OSError as e:
                print(f"NotesOverlay: Error saving notes file - {e}")

            # Copy to clipboard
            try:
                escaped_text = self._escape_text_for_mu(notes_text)
                mu_code = f'require clipboard; clipboard.copyText("{escaped_text}");'
                rv.runtime.eval(mu_code, [])
            except Exception as e:
                print(f"NotesOverlay: Clipboard error - {e}")

        # ---------------------------------------------------------------------
        # Step 6: Export annotated frames as JPGs
        # ---------------------------------------------------------------------
        exported_count = self._export_annotated_frames(source, frames_folder)

        # ---------------------------------------------------------------------
        # Done - show feedback
        # ---------------------------------------------------------------------
        if exported_count > 0 or notes_text:
            extra_commands.displayFeedback(
                f"Review saved: {exported_count} annotated frames, notes copied",
                3.0
            )
        else:
            extra_commands.displayFeedback("No annotations found to export", 2.0)

    def _sanitize_filename(self, name):
        """
        Sanitize a string for use as a filename.

        Removes or replaces characters that are problematic on various filesystems.

        Args:
            name: The string to sanitize.

        Returns:
            str: Sanitized filename-safe string.
        """
        # Characters to remove (problematic on Windows/macOS/Linux)
        invalid_chars = '<>:"/\\|?*'
        result = name
        for char in invalid_chars:
            result = result.replace(char, "_")
        # Remove leading/trailing whitespace and dots
        result = result.strip(". ")
        return result if result else "unnamed"

    def _escape_text_for_mu(self, text):
        """Escape text for embedding in Mu string literal."""
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _strip_sequence_pattern(self, name):
        """
        Strip frame range and padding pattern from image sequence names.

        RV represents image sequences with patterns like:
        - 'shot.30-69@@@' (frame range 30-69, 3-digit padding)
        - 'shot.1001@@@@@' (single frame reference with padding)
        - 'shot.%04d' (printf-style pattern)

        This strips those patterns to get just the base name.

        Args:
            name: The source name (already without file extension).

        Returns:
            str: Base name without frame range/padding pattern.
        """
        import re

        # Pattern 1: .{digits}-{digits}{@s} (e.g., .30-69@@@)
        # Pattern 2: .{digits}{@s} (e.g., .1001@@@)
        # Pattern 3: .{@s} (e.g., .@@@)
        # Pattern 4: .%0{n}d (e.g., .%04d)
        # Pattern 5: .##### (hash padding)
        patterns = [
            r'\.\d+-\d+@+$',      # .30-69@@@
            r'\.\d+@+$',          # .1001@@@
            r'\.@+$',             # .@@@
            r'\.%\d*d$',          # .%04d or .%d
            r'\.#+$',             # .#### or .#####
            r'\.\d+$',            # .1001 (just frame number)
        ]

        result = name
        for pattern in patterns:
            result = re.sub(pattern, '', result)
            if result != name:
                break  # Stop after first match

        return result if result else name

    def _normalize_sequence_path(self, path):
        """
        Normalize image sequence path to standard # padding format.

        Converts RV's sequence notation to standard # format:
        - 'shot.30-69@@@.exr' → 'shot.###.exr'
        - 'shot.1001@@@@.exr' → 'shot.####.exr'
        - 'shot.%04d.exr' → 'shot.####.exr'

        For non-sequences, returns the path unchanged.

        Args:
            path: Full file path.

        Returns:
            str: Path with normalized sequence notation.
        """
        import re

        # Pattern: .{optional digits}{optional dash}{optional digits}{@s}.ext
        # Capture the @ count to determine padding
        match = re.search(r'\.(\d+-\d+)?(@+)(\.[^.]+)$', path)
        if match:
            at_count = len(match.group(2))
            hashes = '#' * at_count
            return re.sub(r'\.\d*-?\d*@+(\.[^.]+)$', f'.{hashes}\\1', path)

        # Pattern: .{digits}{@s}.ext (without range)
        match = re.search(r'\.(\d+)(@+)(\.[^.]+)$', path)
        if match:
            at_count = len(match.group(2))
            hashes = '#' * at_count
            return re.sub(r'\.\d+@+(\.[^.]+)$', f'.{hashes}\\1', path)

        # Pattern: .{@s}.ext (just @s)
        match = re.search(r'\.(@+)(\.[^.]+)$', path)
        if match:
            at_count = len(match.group(1))
            hashes = '#' * at_count
            return re.sub(r'\.@+(\.[^.]+)$', f'.{hashes}\\1', path)

        # Pattern: .%0Nd.ext (printf style)
        match = re.search(r'\.%0?(\d*)d(\.[^.]+)$', path)
        if match:
            num_digits = int(match.group(1)) if match.group(1) else 4
            hashes = '#' * num_digits
            return re.sub(r'\.%0?\d*d(\.[^.]+)$', f'.{hashes}\\1', path)

        # No sequence pattern found, return as-is
        return path

    def _gather_notes_for_export(self, source, frames_folder=None, session_path=None):
        """
        Gather all notes from a source for export.

        Reuses logic from copy_notes_to_clipboard but returns the text
        instead of copying directly to clipboard.

        Args:
            source: The source node to gather notes from.
            frames_folder: Path to exported frames folder (optional, for Save Review).
            session_path: Path to saved RV session file (optional, for Save Review).

        Returns:
            tuple: (formatted_text, total_notes, total_frames)
                - formatted_text: The formatted notes string (or None if no notes)
                - total_notes: Count of text notes
                - total_frames: Count of frames with annotations
        """
        import os

        # Clear stale marks and re-mark annotated frames (ensures accurate state)
        try:
            rv.runtime.eval("require rvui; rvui.clearAllMarks(); rvui.markAnnotatedFrames();", [])
        except Exception:
            pass  # Non-critical

        # Get paint node for this source
        source_group = commands.nodeGroup(source)
        paint_nodes = extra_commands.nodesInGroupOfType(source_group, "RVPaint")

        if not paint_nodes:
            return (None, 0, 0)

        source_paint_node = paint_nodes[0]

        # Find sequence paint node for native RV annotations
        sequence_paint_node = None
        try:
            all_paint_nodes = commands.nodesOfType("RVPaint")
            source_id = source_group.replace("sourceGroup", "")
            for pn in all_paint_nodes:
                if f"_p_sourceGroup{source_id}" in pn or f"_p_{source_group}" in pn:
                    sequence_paint_node = pn
                    break
        except Exception:
            pass

        # Get annotated frames from both paint nodes
        annotated_frames = self.get_annotated_frames(source_paint_node)
        native_frames = []
        if sequence_paint_node:
            native_frames = self.get_annotated_frames(sequence_paint_node)

        all_annotated_frames = sorted(set(annotated_frames) | set(native_frames))

        if not all_annotated_frames:
            return (None, 0, 0)

        # Gather notes for each frame
        frame_notes = {}
        drawing_only_frames = set()

        # Process source paint node frames (our plugin notes)
        for frame in annotated_frames:
            texts, has_drawings = self.get_notes_for_frame(source_paint_node, frame)
            if texts:
                if frame not in frame_notes:
                    frame_notes[frame] = []
                frame_notes[frame].extend(texts)
            elif has_drawings:
                drawing_only_frames.add(frame)

        # Process sequence paint node frames (native RV annotations)
        if sequence_paint_node:
            for global_frame in native_frames:
                try:
                    src_frame = extra_commands.sourceFrame(global_frame)
                except Exception:
                    src_frame = global_frame

                texts, has_drawings = self.get_notes_for_frame(sequence_paint_node, global_frame)
                if texts:
                    if src_frame not in frame_notes:
                        frame_notes[src_frame] = []
                    frame_notes[src_frame].extend(texts)
                elif has_drawings:
                    drawing_only_frames.add(src_frame)

        if not frame_notes and not drawing_only_frames:
            return (None, 0, 0)

        # Get source filename and path for export formatting
        try:
            info = commands.sourceMediaInfo(source)
            source_path = info.get("file", "")
            source_name = os.path.basename(source_path) if source_path else str(source)
        except Exception:
            source_path = ""
            source_name = str(source)

        # Format output
        output_text = self.format_notes_for_export(
            source_name, source_path, frame_notes, drawing_only_frames,
            frames_folder=frames_folder, session_path=session_path
        )

        total_notes = sum(len(notes) for notes in frame_notes.values())
        total_frames = len(frame_notes) + len(drawing_only_frames)

        return (output_text, total_notes, total_frames)

    def _export_annotated_frames(self, source, review_folder):
        """
        Export all annotated frames as JPG files for the current source only.

        Temporarily switches the view to show only the current source, which:
        1. Isolates annotations to this source only
        2. Makes timeline frames equal to source frames

        Uses RV's built-in export functionality via export_utils.exportMarkedFrames.

        Args:
            source: The source node to export frames from.
            review_folder: Path to the folder to save JPGs in.

        Returns:
            int: Number of frames that will be exported.
        """
        import os

        # Get the source group for this source
        source_group = commands.nodeGroup(source)

        # Save current view node to restore later
        try:
            original_view = commands.viewNode()
        except Exception as e:
            print(f"NotesOverlay: Could not get current view - {e}")
            original_view = None

        try:
            # Switch to view only the current source group
            # This isolates the timeline to just this source (source frames = timeline frames)
            try:
                commands.setViewNode(source_group)
            except Exception as e:
                print(f"NotesOverlay: Could not switch view to source - {e}")
                return 0

            # Clear existing marks and mark only annotated frames for this source
            try:
                rv.runtime.eval("require rvui; rvui.clearAllMarks(); rvui.markAnnotatedFrames();", [])
            except Exception as e:
                print(f"NotesOverlay: Could not mark annotated frames - {e}")

            # Get marked frames to count them and determine padding
            try:
                marked_frames = commands.markedFrames()
            except Exception as e:
                print(f"NotesOverlay: Could not get marked frames - {e}")
                marked_frames = []

            # Filter out frames with no visible content (empty text elements)
            # RV marks frames with any paint element, including empty ones
            paint_nodes = extra_commands.nodesInGroupOfType(source_group, "RVPaint")
            if paint_nodes and marked_frames:
                source_paint_node = paint_nodes[0]
                valid_frames = []
                for frame in marked_frames:
                    texts, has_drawings = self.get_notes_for_frame(source_paint_node, frame)
                    # Filter blank texts using the same logic as normalize_note
                    valid_texts = [t for t in texts if self.normalize_note(t)]
                    if valid_texts or has_drawings:
                        valid_frames.append(frame)
                    else:
                        # Frame has only empty text elements - clean them up
                        self._clean_empty_paint_elements(source_paint_node, frame)
                marked_frames = valid_frames

                # Clear RV marks and re-mark only valid frames
                try:
                    rv.runtime.eval("require rvui; rvui.clearAllMarks();", [])
                    for frame in valid_frames:
                        commands.markFrame(frame, True)
                except Exception as e:
                    print(f"NotesOverlay: Could not update marks - {e}")

            exported_count = 0

            if marked_frames:
                # Determine number of digits needed for frame numbers
                # Use at least 4 digits for consistency, but more if needed
                max_frame = max(marked_frames)
                num_digits = max(4, len(str(max_frame)))

                # Build frame pattern (e.g., "####" for 4 digits)
                frame_pattern = "#" * num_digits

                # Build output path pattern
                jpg_pattern = os.path.join(review_folder, f"{frame_pattern}.jpg")

                # Reset view to fit image in viewport before export
                try:
                    rv.runtime.eval("require extra_commands; extra_commands.frameImage();", [])
                except Exception as e:
                    print(f"NotesOverlay: Could not frame view - {e}")

                # Reset all color corrections before export
                try:
                    rv.runtime.eval("require rvui; rvui.resetAllColorParameters();", [])
                except Exception as e:
                    print(f"NotesOverlay: Could not reset color - {e}")

                # Call RV's export function
                try:
                    escaped_path = jpg_pattern.replace("\\", "/")
                    mu_code = f'require export_utils; export_utils.exportMarkedFrames("{escaped_path}", "default");'
                    rv.runtime.eval(mu_code, [])
                    exported_count = len(marked_frames)
                except Exception as e:
                    print(f"NotesOverlay: Error exporting frames - {e}")

            return exported_count
        finally:
            # Restore original view
            if original_view:
                try:
                    commands.setViewNode(original_view)
                except Exception as e:
                    print(f"NotesOverlay: Could not restore view - {e}")

    # -------------------------------------------------------------------------
    # Copy Notes
    # -------------------------------------------------------------------------

    def copy_notes_to_clipboard(self, event):
        """
        Copy all notes from current source to clipboard.

        Gathers notes from all annotated frames (including RV native annotations),
        deduplicates, unwraps line breaks, formats chronologically by source frame,
        and copies to clipboard.

        Supports:
        - Our plugin's notes (text:*:*:note elements)
        - RV native text annotations (text:* elements)
        - Drawing-only frames (shows "See annotated frame" placeholder)
        """
        import os

        # Clear stale marks and re-mark annotated frames (ensures accurate state)
        # This invokes RV's "Edit > Mark Annotated Frames" menu action via Mu
        try:
            rv.runtime.eval("require rvui; rvui.clearAllMarks(); rvui.markAnnotatedFrames();", [])
        except Exception as e:
            # Non-critical - frames may already be marked or function unavailable
            print(f"NotesOverlay: markAnnotatedFrames failed (non-critical): {e}")

        # Get current source
        current_frame = commands.frame()
        sources = commands.sourcesAtFrame(current_frame)

        if not sources:
            extra_commands.displayFeedback("No source at current frame", 2.0)
            return

        source = sources[0]

        # Get paint node for this source
        source_group = commands.nodeGroup(source)
        paint_nodes = extra_commands.nodesInGroupOfType(source_group, "RVPaint")

        if not paint_nodes:
            extra_commands.displayFeedback("See annotation - no text notes found", 2.0)
            return

        source_paint_node = paint_nodes[0]

        # Find the sequence paint node for native RV annotations
        # Native annotations are stored on "defaultSequence_p_{sourceGroup}" nodes
        sequence_paint_node = None
        try:
            all_paint_nodes = commands.nodesOfType("RVPaint")
            # Look for sequence paint node matching this source
            source_id = source_group.replace("sourceGroup", "")  # e.g., "000000"
            for pn in all_paint_nodes:
                if f"_p_sourceGroup{source_id}" in pn or f"_p_{source_group}" in pn:
                    sequence_paint_node = pn
                    break
        except Exception as e:
            print(f"NotesOverlay: Error finding sequence paint node: {e}")

        # Get frames from source paint node (our notes - source frame numbers)
        annotated_frames = self.get_annotated_frames(source_paint_node)

        # Get frames from sequence paint node (native annotations - global frame numbers)
        native_frames = []
        if sequence_paint_node:
            native_frames = self.get_annotated_frames(sequence_paint_node)

        # Combine both frame lists (they use different numbering, will handle in gathering)
        all_annotated_frames = sorted(set(annotated_frames) | set(native_frames))

        if not all_annotated_frames:
            extra_commands.displayFeedback("No annotations found", 2.0)
            return

        # Gather notes for each frame from BOTH paint nodes
        # Note: source paint node uses source frames, sequence paint node uses global frames
        frame_notes = {}  # frame -> list of texts
        drawing_only_frames = set()  # frames with only drawings (no text)

        # Process source paint node frames (our plugin notes)
        for frame in annotated_frames:
            texts, has_drawings = self.get_notes_for_frame(source_paint_node, frame)
            if texts:
                if frame not in frame_notes:
                    frame_notes[frame] = []
                frame_notes[frame].extend(texts)
            elif has_drawings:
                drawing_only_frames.add(frame)

        # Process sequence paint node frames (native RV annotations)
        # These use global frame numbers - convert to source frame for display
        if sequence_paint_node:
            for global_frame in native_frames:
                # Convert global frame to source frame for consistent display
                try:
                    src_frame = extra_commands.sourceFrame(global_frame)
                except Exception:
                    src_frame = global_frame

                texts, has_drawings = self.get_notes_for_frame(sequence_paint_node, global_frame)
                if texts:
                    if src_frame not in frame_notes:
                        frame_notes[src_frame] = []
                    frame_notes[src_frame].extend(texts)
                elif has_drawings:
                    drawing_only_frames.add(src_frame)

        if not frame_notes and not drawing_only_frames:
            extra_commands.displayFeedback("No annotations found", 2.0)
            return

        # Get source filename and path for export
        try:
            info = commands.sourceMediaInfo(source)
            source_path = info.get("file", "")
            source_name = os.path.basename(source_path) if source_path else source
        except Exception:
            source_path = ""
            source_name = source

        # Format output (pass drawing_only_frames for placeholder handling)
        output_text = self.format_notes_for_export(
            source_name, source_path, frame_notes, drawing_only_frames
        )

        # Copy to clipboard via Mu
        try:
            escaped_text = self._escape_text_for_mu(output_text)
            mu_code = f'require clipboard; clipboard.copyText("{escaped_text}");'
            rv.runtime.eval(mu_code, [])

            # Count total annotations for feedback
            total_notes = sum(len(notes) for notes in frame_notes.values())
            total_frames = len(frame_notes) + len(drawing_only_frames)
            drawing_suffix = f" + {len(drawing_only_frames)} drawings" if drawing_only_frames else ""
            extra_commands.displayFeedback(
                f"Notes copied! ({total_notes} notes from {total_frames} frames{drawing_suffix})",
                2.5
            )

        except Exception as e:
            extra_commands.displayFeedback("Failed to copy to clipboard", 2.0)
            print(f"NotesOverlay: Clipboard error - {e}")

    def get_annotated_frames(self, paint_node):
        """
        Get all frames with ANY paint elements for a given paint node.

        Scans the paint node properties for frame order entries and extracts
        unique frame numbers that have any annotations (text, strokes, shapes, etc.).

        Filters out our shadow elements (shadow0-7) which are just outline effects.

        Args:
            paint_node: The RVPaint node name to scan.

        Returns:
            list: Sorted list of frame numbers with annotations.
        """
        frames = set()

        # Shadow labels to skip (our outline effect elements)
        shadow_labels = {f":shadow{i}" for i in range(8)}

        try:
            # Get all properties on the paint node
            properties = commands.properties(paint_node)

            # Look for frame order properties (e.g., "node.frame:123.order")
            for prop in properties:
                if ".order" in prop:
                    # Extract frame number from property name
                    # Format: "paintNode.frame:{frame}.order"
                    parts = prop.split(".")
                    for part in parts:
                        if part.startswith("frame:"):
                            try:
                                frame_num = int(part.split(":")[1])
                                # Check if frame has any real elements (not just shadows)
                                order_data = commands.getStringProperty(prop)
                                for element in order_data:
                                    # Skip shadow elements (our outline effect)
                                    is_shadow = any(element.endswith(s) for s in shadow_labels)
                                    if not is_shadow:
                                        frames.add(frame_num)
                                        break
                            except (ValueError, IndexError):
                                pass

        except Exception as e:
            print(f"NotesOverlay: Error getting annotated frames: {e}")

        return sorted(frames)

    def _clean_empty_paint_elements(self, paint_node, frame):
        """
        Remove empty text elements from a frame's paint data.

        RV's native text tool can create text elements with no content.
        These cause the frame to be marked as "annotated" even though
        nothing is visible. This method clears those empty elements using
        RV's native "Clear Drawings" action.

        Only removes elements if the frame has NO valid content (no text,
        no drawings). If there's any real annotation, leaves everything.

        Args:
            paint_node: The RVPaint node name.
            frame: The frame number to clean.

        Returns:
            bool: True if elements were deleted, False otherwise.
        """
        shadow_labels = {f":shadow{i}" for i in range(8)}
        drawing_types = {"stroke", "line", "rect", "circle", "pen", "arrow"}

        try:
            order_prop = f"{paint_node}.frame:{frame}.order"

            if not commands.propertyExists(order_prop):
                return False

            order_data = commands.getStringProperty(order_prop)
            if not order_data:
                return False

            has_valid_content = False
            empty_text_elements = []

            for element in order_data:
                # Skip shadow elements
                is_shadow = any(element.endswith(s) for s in shadow_labels)
                if is_shadow:
                    continue

                element_type = element.split(":")[0] if ":" in element else ""

                # Check for text content
                text_prop = f"{paint_node}.{element}.text"
                if commands.propertyExists(text_prop):
                    note_text = commands.getStringProperty(text_prop)[0]
                    if note_text and note_text.strip():
                        has_valid_content = True
                    else:
                        # Empty text element
                        empty_text_elements.append(element)
                elif element_type in drawing_types:
                    has_valid_content = True

            # Only clear if there's NO valid content
            if has_valid_content or not empty_text_elements:
                return False

            # Navigate to the frame and use RV's native clear action
            try:
                # Save current frame
                original_frame = commands.frame()

                # Go to the frame with empty annotations
                commands.setFrame(frame)

                # Trigger RV's "Clear Drawings" action for current frame
                # This is the internal event bound to Annotations > Clear Drawings
                commands.sendInternalEvent("clear-annotations-current-frame", "", "")

                # Return to original frame
                commands.setFrame(original_frame)

                return True
            except Exception as e:
                print(f"NotesOverlay: Could not clear empty paint elements - {e}")
                return False

        except Exception as e:
            print(f"NotesOverlay: Error cleaning paint elements for frame {frame}: {e}")
            return False

    def get_notes_for_frame(self, paint_node, frame):
        """
        Get all text annotations and detect non-text content for a frame.

        Reads all paint elements from the paint node:
        - Extracts text from any element with a .text property
        - Detects non-text annotations (strokes, lines, shapes)
        - Filters out shadow elements (our outline effect)
        - Deduplicates by exact text match

        Args:
            paint_node: The RVPaint node name.
            frame: The frame number (source frame for our notes, global for native).

        Returns:
            tuple: (list of text strings, bool has_drawings)
                - texts: List of unique note/text strings
                - has_drawings: True if frame has non-text elements (strokes, shapes)
        """
        texts = []
        seen_texts = set()
        has_drawings = False

        # Shadow labels to skip (our outline effect elements)
        shadow_labels = {f":shadow{i}" for i in range(8)}

        # Element types that are drawing-based (non-text)
        drawing_types = {"stroke", "line", "rect", "circle", "pen", "arrow"}

        try:
            order_prop = f"{paint_node}.frame:{frame}.order"

            if commands.propertyExists(order_prop):
                order_data = commands.getStringProperty(order_prop)

                for element in order_data:
                    # Skip shadow elements (our outline effect)
                    is_shadow = any(element.endswith(s) for s in shadow_labels)
                    if is_shadow:
                        continue

                    # Parse element type from format: "type:id:frame:label"
                    element_type = element.split(":")[0] if ":" in element else ""

                    # Check for text content (text elements have .text property)
                    text_prop = f"{paint_node}.{element}.text"
                    if commands.propertyExists(text_prop):
                        note_text = commands.getStringProperty(text_prop)[0]
                        if note_text and note_text.strip():
                            # Deduplicate by exact text match
                            if note_text not in seen_texts:
                                seen_texts.add(note_text)
                                texts.append(note_text)
                    elif element_type in drawing_types:
                        # Non-text element (stroke, line, shape, etc.)
                        has_drawings = True

        except Exception as e:
            print(f"NotesOverlay: Error reading notes for frame {frame}: {e}")

        return (texts, has_drawings)

    def unwrap_note(self, text):
        """
        Restore original note text by removing display formatting.

        Removes the bullet prefix and line breaks that were added for
        on-screen display, returning the original user-entered text.

        Args:
            text: The wrapped note text (may or may not have bullet prefix).

        Returns:
            str: The original unwrapped text (without bullet prefix).
        """
        # Strip leading bullet prefix (our notes are stored as "- text")
        if text.startswith("- "):
            text = text[2:]

        # Replace newlines with single space (undo line wrapping)
        text = text.replace("\n", " ")

        # Collapse multiple spaces to single space
        while "  " in text:
            text = text.replace("  ", " ")

        # Strip leading/trailing whitespace
        return text.strip()

    def normalize_note(self, text):
        """
        Normalize a note for export by unwrapping and ensuring dash prefix.

        Unwraps the text (removes line breaks) and ensures it has a
        consistent `- ` prefix for uniform formatting in export.

        Args:
            text: The raw note text from RVPaint.

        Returns:
            str: Normalized text with `- ` prefix, or None if note is blank.
        """
        # First unwrap the text
        unwrapped = self.unwrap_note(text)

        # Filter out blank notes (empty or whitespace-only after unwrapping)
        if not unwrapped:
            return None

        # Ensure it has a dash prefix
        if not unwrapped.startswith("-"):
            return f"- {unwrapped}"
        else:
            # Already has dash - ensure proper spacing
            content_after_dash = unwrapped[1:].strip() if len(unwrapped) > 1 else ""
            # If only a dash with no content, treat as blank
            if not content_after_dash:
                return None
            if unwrapped.startswith("- "):
                return unwrapped
            else:
                return f"- {content_after_dash}"

        return unwrapped

    def format_notes_for_export(self, source_name, source_path, frame_notes, drawing_only_frames=None,
                                frames_folder=None, session_path=None):
        """
        Format notes for clipboard export.

        Creates a formatted string with:
        - Header: source name + datetime
        - Body: frame numbers with notes (compact, no separators)
        - Footer: source file path

        For frames with only drawings (no text), shows "See annotated frame".

        Args:
            source_name: The source filename to display in header.
            source_path: The full file path for footer metadata.
            frame_notes: Dict mapping frame numbers to lists of note texts.
            drawing_only_frames: Set of frame numbers with only drawings (optional).
            frames_folder: Path to exported frames folder (optional, from Save Review).
            session_path: Path to saved RV session file (optional, from Save Review).

        Returns:
            str: Formatted notes string ready for clipboard.

        Output format:
            Notes on shot_010_v002.mov
            2026-01-28 06:30

            ---

            Frame 1001
            - First note
            - Second note

            Frame 1004
            - Another note

            Frame 1010
            - See annotated frame

            ---

            /path/to/shot_010_v002.mov
        """
        from datetime import datetime

        if drawing_only_frames is None:
            drawing_only_frames = set()

        # Normalize sequence names to standard # format
        normalized_source_name = self._normalize_sequence_path(source_name)

        lines = []

        # Header: source name + datetime
        lines.append(f"Notes on {normalized_source_name}")
        lines.append(datetime.now().strftime("%Y_%m_%d %H:%M"))
        lines.append("")
        lines.append("---")
        lines.append("")

        # Combine all frames (text notes + drawing-only)
        all_frames = sorted(set(frame_notes.keys()) | drawing_only_frames)

        # Body: frames with notes (blank line between groups, no separators)
        for i, frame in enumerate(all_frames):
            # Frame number as section header
            lines.append(f"Frame {frame}")

            if frame in frame_notes:
                # Frame has text notes
                notes = frame_notes[frame]
                valid_notes = []
                for note in notes:
                    normalized = self.normalize_note(note)
                    if normalized:  # Skip blank notes (normalize_note returns None)
                        valid_notes.append(normalized)
                        lines.append(normalized)
                # If all notes were blank, treat as drawing-only
                if not valid_notes:
                    lines.append("- *see annotated frame")
            else:
                # Drawing-only frame - show placeholder (asterisk prefix to differentiate)
                lines.append("- *see annotated frame")

            # Blank line between frame groups (but not after last)
            if i < len(all_frames) - 1:
                lines.append("")

        # Footer: separator + file paths
        lines.append("")
        lines.append("---")
        lines.append("")

        # Review export paths first (only when Save Review was used)
        if frames_folder:
            lines.append("annotations:")
            lines.append(frames_folder)
            lines.append("")
        if session_path:
            lines.append("session:")
            lines.append(session_path)
            lines.append("")

        # Separator between review paths and source info
        if frames_folder or session_path:
            lines.append("---")
            lines.append("")

        # Source file path
        lines.append("source file:")
        if source_path:
            # Normalize sequence paths to standard # format
            normalized_path = self._normalize_sequence_path(source_path)
            lines.append(normalized_path)
        else:
            lines.append(source_name)

        # Source folder path
        if source_path:
            import os
            source_folder = os.path.dirname(source_path)
            lines.append("")
            lines.append("source folder:")
            lines.append(source_folder)

        return "\n".join(lines)


# -----------------------------------------------------------------------------
# Module Entry Point (required by RV package system)
# -----------------------------------------------------------------------------

# Global mode instance
_mode_instance = None


def createMode():
    """
    Create and return the mode instance.

    This function is called by RV's package system when loading the package.
    Returns a singleton instance of NotesOverlayMode.
    """
    global _mode_instance
    _mode_instance = NotesOverlayMode()
    return _mode_instance
