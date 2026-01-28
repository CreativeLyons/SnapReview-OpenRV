# -----------------------------------------------------------------------------
# NotesOverlay - OpenRV Review Notes Plugin
# -----------------------------------------------------------------------------
# Adds a "Review > Add Note" menu to OpenRV for adding text annotations
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
    - Review > Add Note menu item (shift+n hotkey)
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
                # Internal event for receiving text from Mu dialog
                ("notes-overlay-text-entered", self._on_text_entered, "Handle entered note text"),
            ],
            None,  # No override bindings
            # Menu structure: (menu_name, [(item_name, callback, hotkey, state_hook), ...])
            [
                ("Review", [
                    ("Add Note", self.open_note_dialog, "N", None),
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
        self._pending_note_frame = commands.frame()

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
        except Exception:
            source_frame = frame

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
        self._draw_note_with_outline_on_frame(paint_node, source_frame, wrapped_note, existing_notes)

        # Mark the frame on the timeline so user can see which frames have notes
        commands.markFrame(frame, True)

        # Force redraw
        commands.redraw()

    def _draw_note_with_outline_on_frame(self, paint_node, frame, text, line_offset):
        """
        Draw note text with black outline effect on a specific frame.

        Creates 4 shadow texts at offset positions (black) and one main text (white)
        to create an outline effect for readability.

        Args:
            paint_node: The RVPaint node to draw on.
            frame: The frame number.
            text: Note text to display.
            line_offset: Vertical offset based on existing notes (in lines).
        """
        scale = self.get_image_scale()

        # Get image dimensions from source media info
        try:
            sources = commands.sourcesAtFrame(commands.frame())
            if sources:
                info = commands.sourceMediaInfo(sources[0])
                img_w = info.get("width", 1920)
                img_h = info.get("height", 1080)
                aspect = img_w / img_h
            else:
                aspect = 16 / 9  # Default 16:9
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
        shadow_offset = 0.002  # Thicker outline
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
    SHADOW_OFFSET = 0.002

    # -------------------------------------------------------------------------
    # Note Adding Methods
    # -------------------------------------------------------------------------

    def get_image_scale(self):
        """
        Calculate text scale factor based on source image dimensions.

        Normalizes text size relative to a 1080p reference so text appears
        similarly sized regardless of source resolution.

        Returns:
            float: Scale factor for text size.
        """
        try:
            view_frame = commands.frame()
            sources = commands.sourcesAtFrame(view_frame)

            if sources:
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
