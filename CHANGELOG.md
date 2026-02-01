# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🐞 Fixed

- Restored view node after errors while checking annotations in Save Review.
- Used the explicit frame when computing note scale/aspect for render accuracy.
- Aborted note creation when source frame conversion fails to prevent wrong-frame notes.
- Ensured view node restoration after exporting annotated frames, even on errors.
- Extracted `_escape_text_for_mu()` helper to deduplicate Mu string escaping in Save Review and Copy Notes (Fixed issue #16).
- Removed unused `_open_note_dialog_legacy()` method (Fixed issue #13).
- Removed unused PySide imports and variables (Fixed issue #12).
- Use `SHADOW_OFFSET` constant instead of hardcoded value in note outline (Fixed issue #17).
- Guard against division by zero when source height is 0 in `get_image_scale()` (Fixed issue #14).
- Removed unused `setPendingText()`, `copyPending()`, and `_pendingText` from clipboard.mu (Fixed issue #18).
- Session save failure now indicated in final feedback when Save Review partially fails (Fixed issue #11).
- Removed empty `requires` field from PACKAGE manifest (Fixed issue #15).

## [1.5.0] - 2026-01-29

### 🔄 Changed

- **Renamed to SnapReview** — Product renamed from NotesOverlay to SnapReview
  - RV menu now displays as `SnapReview` instead of `Review`
  - Menu items: `Add Note`, `Copy Notes`, `Save Review`
  - Package renamed to `SnapReview.rvpkg`
  - All documentation updated to reflect new branding
  - Python module remains `NotesOverlay.py` (internal implementation)
- **Save Review Message** — Updated feedback to `Review saved: X annotated frames, notes copied`

### 🐞 Fixed

- **Empty Text Elements** — Fixed issue where clicking RV's text tool without typing would:
  - Mark frames as "annotated" even though nothing was visible
  - Export blank frames during Save Review
  - Show empty dashes in copied notes
- **Blank Note Filtering** — `normalize_note()` now returns `None` for blank notes
  - Notes that are empty or contain only dashes are excluded from export
  - Frames with only blank notes show `*see annotated frame` placeholder
- **Stale Marks Cleanup** — Added `clearAllMarks()` before `markAnnotatedFrames()` at all entry points
  - Ensures timeline reflects accurate annotation state
- **Empty Paint Element Cleanup** — New `_clean_empty_paint_elements()` method
  - Detects frames with only empty text elements (no valid text, no drawings)
  - Uses RV's native `clear-annotations-current-frame` event to remove them
  - Cleans up automatically during Save Review

### 🔧 Technical

- Uses `commands.sendInternalEvent("clear-annotations-current-frame", "", "")` to invoke RV's native clear
- Filters marked frames before export to exclude empty-only frames
- Re-marks only valid frames using `commands.markFrame()` after filtering

## [1.4.0] - 2026-01-29

### ✨ Added

- **Save Review** — New menu item and `Cmd+Shift+S` / `Ctrl+Shift+S` hotkey
  - Creates timestamped folder next to source file: `{YYYY_MM_DD_HHMMSS}_{source}-review/`
  - Exports RV session file (`{source}-review_session.rv`)
  - Exports notes to text file (`{source}_review_notes.txt`)
  - Exports annotated frames as JPGs in `frames/` subfolder with zero-padded frame numbers
  - Copies notes to clipboard (same as Copy Notes)
- **Source Isolation** — Automatically switches to current source view before export
  - Only exports annotations from the source you're standing on
  - Frame numbers are source-relative, not timeline-relative
- **Color Reset on Export** — Calls `resetAllColorParameters()` before exporting frames
  - Ensures exported frames show original colors without user adjustments
- **View Reset on Export** — Calls `frameImage()` to fit image in viewport before export
- **Early Exit** — Bails out immediately with feedback if no annotations found
- **Notes Footer Enhancement** — Footer now includes:
  - `annotations:` path to exported frames folder
  - `session:` path to saved RV session
  - `source file:` path to source media
  - `source folder:` directory containing source

### 🔄 Changed

- **Shadow Outline** — Increased from `0.002` to `0.003` (1.5x) for better readability over white backgrounds
- **Notes Footer Format** — Labels on separate lines from paths for cleaner copy/paste
- **Image Sequence Handling** — Strips frame range patterns (`.30-69@@@`) from folder names
  - Normalizes paths in notes footer to `###` format for application compatibility

### 🔧 Technical

- New `save_review()` method orchestrates folder creation, session save, notes export, and frame export
- New `_export_annotated_frames()` uses RV's `export_utils.exportMarkedFrames()` with rvio
- New `_gather_notes_for_export()` extracts notes gathering logic for reuse
- New `_sanitize_filename()` removes filesystem-unsafe characters
- New `_strip_sequence_pattern()` handles various sequence notations (@@, %04d, ####)
- New `_normalize_sequence_path()` converts RV sequence notation to standard `#` format
- Uses `setViewNode()` to isolate source before marking/exporting
- Frame padding auto-calculated from max frame number (minimum 4 digits)

## [1.3.0] - 2026-01-28

### ✨ Added

- **Copy Notes** — New menu item and `Cmd+Shift+C` / `Ctrl+Shift+C` hotkey
  - Exports all notes from current source in chronological order by frame
  - Header with source name and timestamp, footer with file path
  - Markdown-friendly format with bullet points per note
- **RV Native Annotation Support** — Detects both plugin notes AND RV's native paint annotations
  - Scans sequence paint nodes for annotations made with RV's built-in tools
  - Marks annotated frames via `markAnnotatedFrames()` before gathering
- **Drawing Placeholder** — Frames with only drawings (no text) show `- *see annotated frame`

### 🔧 Technical

- New `clipboard.mu` module for clipboard access via Qt's QApplication.clipboard()
- Discovered native RV annotations stored on `defaultSequence_p_*` paint nodes (global frames)
- Added `normalize_note()` helper to ensure consistent `- ` prefix formatting
- Updated `get_annotated_frames()` and `get_notes_for_frame()` to scan multiple paint nodes

## [1.2.0] - 2026-01-28

### ✨ Added

- Dialog title displays source frame number ("Add Note @ Frame 1001")
- Validation check prevents opening dialog when no source at current frame
- Slack-style keyboard shortcuts via custom NoteTextEdit subclass:
  - Enter submits note (like sending a message)
  - Shift+Enter inserts newline
  - Escape cancels
  - Enter on empty text cancels (same as Escape)

### 🔄 Changed

- Removed Add/Cancel buttons for keyboard-only interaction
- More minimal dialog appearance: 55px height, 4px margins
- Updated placeholder text with keyboard shortcut hints

### 🔧 Technical

- Custom `NoteTextEdit` class overrides `keyPressEvent` for key handling
- Key learning: class member variables required (module globals inaccessible from class methods in Mu)
- Added `docs/DEVELOPMENT.md` with Mu/Qt development learnings

## [1.1.0] - 2026-01-28

### 🔄 Changed

- Replaced native text entry with custom Qt dialog for note input
  - Multi-line text editing with proper copy/paste support (Cmd+C/V)
  - Rich text formatting stripped on paste (plain text only)
  - Dialog positioned at bottom of RV window for minimal obstruction

### 🔧 Technical

- New `notes_dialog.mu` module using RV's Mu Qt bindings
- Documented key Mu/Qt learnings in code comments:
  - QPushButton.clicked requires `(void; bool checked)` callback signature
  - Closures don't work in Mu; use module-level globals
  - Widget constructor signatures vary (QLabel vs QPushButton vs QTextEdit)
  - Use `sendInternalEvent()` for Mu-to-Python communication

## [1.0.0] - 2026-01-27

### ✨ Added

- **SnapReview plugin** — Text annotation overlay for OpenRV
  - `SnapReview > Add Note` menu item with `Shift+N` hotkey
  - White text with black outline for readability on any background
  - Smart text wrapping with configurable line length
  - Vertical stacking of multiple notes per frame
  - Multi-source support — correctly handles sequences with multiple clips
  - Timeline markers automatically added to frames with notes
  - Notes persist in RVPaint node properties (survives session save/autosave)

### 🔧 Technical

- Uses `extra_commands.sourceFrame()` for accurate frame mapping in sequences
- Configurable constants for text size, line spacing, and character limits
- Automatic line wrapping: 58 chars for sentences, 37 chars for single words
- 8-point shadow outline (4 corners + 4 cardinals) for text legibility

### 📦 Dependencies

- Initial `.gitignore` for Python, IDE, and build artifacts
- `PACKAGE` manifest for OpenRV package distribution
- Pre-built `SnapReview.rvpkg` ready for download
- Documentation and changelog structure
