# SnapReview Development Notes

This document captures key learnings, decisions, and work-in-progress for AI agents and developers working on this project.

## Architecture Overview

```
NotesOverlay.py          Python MinorMode plugin for OpenRV
    │
    └── calls via rv.runtime.eval() ──►  notes_dialog.mu
                                              │
                                              └── Mu module using Qt bindings
                                                  Creates QDialog with QTextEdit
                                                  Returns text via sendInternalEvent()
```

**Why Mu instead of PySide?**
- PySide2/6 is not reliably available in all OpenRV builds
- Mu has direct access to Qt via RV's Qt bindings (`use qt;`)
- Pattern used by RV's own `annotate_mode.mu`

## Key Mu/Qt Learnings

These discoveries were hard-won through trial and error:

### 1. Signal Callback Signatures
QPushButton.clicked passes a `bool checked` parameter. Callbacks MUST have signature:
```mu
\: doAccept (void; bool checked) { ... }  // CORRECT
\: doAccept (void;) { ... }               // WRONG - silent failure!
```

### 2. Closures Don't Work
You cannot reference local variables from enclosing function scope in callbacks.
Use module-level globals instead:
```mu
QDialog _dlg;  // Module-level global
QTextEdit _txt;
```

### 3. Widget Constructor Signatures Vary
```mu
QLabel(text, parent, flags)    // Requires all 3 args
QPushButton(text, parent)      // 2 args
QTextEdit(parent)              // 1 arg
QVBoxLayout(parent)            // Optional parent
QHBoxLayout()                  // No args
```

### 4. Communication Back to Python
```mu
sendInternalEvent("event-name", contentString, "");
```
Python binds the event name in `MinorMode.init()`.

### 5. QDialog.exec() Return Values
- Returns `1` for Accepted
- Returns `0` for Rejected

### 6. Qt Key Event Constants Available in Mu
Verified in `qt.so`:
- `Qt.Key_Return`, `Qt.Key_Enter`, `Qt.Key_Escape`
- `Qt.ControlModifier`, `Qt.ShiftModifier`
- `QKeyEvent` type, `keyPressEvent` method

### 7. Subclassing QTextEdit for Custom Key Handling
To override key behavior in QTextEdit:
```mu
class: NoteTextEdit : QTextEdit
{
    QDialog _parentDialog;  // Store reference to parent

    method: NoteTextEdit (NoteTextEdit; QDialog dialog)
    {
        QTextEdit.QTextEdit(this, dialog);
        _parentDialog = dialog;  // Save for later use
    }

    method: keyPressEvent (void; QKeyEvent event)
    {
        if (event.key() == Qt.Key_Return)
        {
            _parentDialog.accept();  // Use stored reference
            return;
        }
        QTextEdit.keyPressEvent(this, event);
    }
}
```
**Critical:** Store parent as class member. Module-level globals can't be accessed from class methods.

## Things That Didn't Work

| Attempt | Result | Notes |
|---------|--------|-------|
| PySide2 import in Python | "Incompatible processor" error | macOS ARM vs x86 issue |
| QInputDialog.getMultiLineText via Mu | Function not found | Only getText available |
| QShortcut/QKeySequence | May not be exposed | Avoided, using keyPressEvent instead |
| Closures in Mu callbacks | Silent failures | Use module globals |

## Copy Notes / Export Feature Learnings

### Note Sources
The plugin gathers notes from two paint nodes:
1. **Source paint node** — Our plugin's notes (stored with `:note` label suffix)
2. **Sequence paint node** — RV's native text annotations (format: `_p_sourceGroup{id}`)

```python
# Find sequence paint node for native annotations
all_paint_nodes = commands.nodesOfType("RVPaint")
source_id = source_group.replace("sourceGroup", "")
for pn in all_paint_nodes:
    if f"_p_sourceGroup{source_id}" in pn:
        sequence_paint_node = pn
        break
```

### Filtering Blank Notes
Notes are validated before export to exclude empty content:
```python
def normalize_note(self, text):
    unwrapped = self.unwrap_note(text)
    if not unwrapped:
        return None  # Empty
    if unwrapped.startswith("-"):
        content = unwrapped[1:].strip()
        if not content:
            return None  # Just a dash
    return f"- {content}"
```

### Drawing-Only Frames
Frames with drawings but no text show a placeholder:
```python
if valid_texts or has_drawings:
    valid_frames.append(frame)
# In export:
if not valid_texts:
    lines.append("- *see annotated frame")
```

## Save Review Feature Learnings

### Isolating a Source for Export
To export only annotations from the current source (not all sources in timeline):
```python
# Save current view
original_view = commands.viewNode()

# Switch to view only the source group
source_group = commands.nodeGroup(source)
commands.setViewNode(source_group)

# Now timeline frames = source frames
# Mark and export...

# Restore original view
commands.setViewNode(original_view)
```

### Exporting Annotated Frames with rvio
RV's `exportMarkedFrames` uses rvio to render frames. Use `#` for frame number substitution:
```python
# Mark annotated frames
rv.runtime.eval("require rvui; rvui.clearAllMarks(); rvui.markAnnotatedFrames();", [])

# Export with frame pattern (#### = 4 digits, e.g., 0001.jpg)
rv.runtime.eval('require export_utils; export_utils.exportMarkedFrames("/path/####.jpg", "default");', [])
```
The number of `#` determines zero-padding.

### Resetting View Before Export
Two important resets before exporting frames:
```python
# Fit image to viewport (not resize window) - equivalent to 'f' key
rv.runtime.eval("require extra_commands; extra_commands.frameImage();", [])

# Reset color corrections - equivalent to Color > Reset All Color
rv.runtime.eval("require rvui; rvui.resetAllColorParameters();", [])
```

### Image Sequence Path Patterns
RV represents sequences with various notations:
- `.30-69@@@.exr` — frame range 30-69, 3-digit padding
- `.1001@@@.exr` — single frame reference with padding
- `.%04d.exr` — printf-style
- `.####.exr` — hash padding

To normalize for display, convert to standard `#` format:
```python
# .30-69@@@ → .###
re.sub(r'\.\d+-\d+@+(\.[^.]+)$', f'.{hashes}\\1', path)
```

### Python vs Mu Commands
Some commands exist in Mu but not Python:
```python
# This fails - no clearAllMarks in Python
commands.clearAllMarks()  # AttributeError!

# Use Mu instead
rv.runtime.eval("require rvui; rvui.clearAllMarks();", [])
```

Common Mu-only functions:
- `rvui.clearAllMarks()`
- `rvui.markAnnotatedFrames()`
- `rvui.resetAllColorParameters()`
- `extra_commands.frameImage()`
- `export_utils.exportMarkedFrames()`

### Clearing Annotations via Internal Events

RV's `Annotations > Clear Drawings` menu action can be triggered programmatically:
```python
# Navigate to frame, clear, return
original_frame = commands.frame()
commands.setFrame(target_frame)
commands.sendInternalEvent("clear-annotations-current-frame", "", "")
commands.setFrame(original_frame)
```

Available annotation events (from `annotate_mode.mu`):
- `clear-annotations-current-frame` — Clear drawings on current frame
- `clear-annotations-all-frames` — Clear all drawings (shows confirmation dialog)

This is useful for cleaning up empty paint elements that RV's `markAnnotatedFrames()` incorrectly marks as annotated (e.g., text tool clicks with no content).

## Text Rendering Constants

Configurable constants in `NotesOverlay.py`:

```python
TEXT_SIZE = 0.005           # Relative to image height (0.5%)
MAX_CHARS_PER_LINE = 58     # Calculated: 0.29 / TEXT_SIZE
FORCE_BREAK_LENGTH = 37     # Force break long words (65% of max)
LINE_SPACING = 0.08         # 8% of image height between lines
SHADOW_OFFSET = 0.003       # Outline offset for readability
```

**Relationship:** `max_chars = 0.29 / TEXT_SIZE`
- At 0.005 → 58 chars
- At 0.004 → 72 chars
- At 0.006 → 48 chars

## Clipboard Module

`clipboard.mu` provides system clipboard access via Qt:

```python
# From Python, copy text to clipboard:
escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
rv.runtime.eval(f'require clipboard; clipboard.copyText("'{escaped}'");', [])

# For complex strings with special characters, use two-step approach:
rv.runtime.eval('require clipboard; clipboard.setPendingText("...");', [])
rv.runtime.eval('require clipboard; clipboard.copyPending();', [])
```

## File Reference

| File | Purpose |
|------|---------|
| `NotesOverlay.py` | Main Python plugin (MinorMode) |
| `notes_dialog.mu` | Custom Qt dialog for text input |
| `clipboard.mu` | Clipboard access via Qt's QClipboard |
| `PACKAGE` | RV package manifest |
| `SnapReview.rvpkg` | Installable package (zip of above) |

## Testing

1. Symlink files to RV plugin directories:
   ```bash
   # macOS
   ln -s /path/to/NotesOverlay.py ~/Library/Application\ Support/RV/Python/
   ln -s /path/to/notes_dialog.mu ~/Library/Application\ Support/RV/Mu/
   ```

2. Restart RV after changes

3. Test via `SnapReview > Add Note` menu or `Shift+N` hotkey

## Build from Source

```bash
zip -r SnapReview.rvpkg PACKAGE NotesOverlay.py notes_dialog.mu clipboard.mu
```

## Fixes

- Fixed issue #7
