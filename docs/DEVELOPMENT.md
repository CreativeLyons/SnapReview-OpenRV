# NotesOverlay Development Notes

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

## File Reference

| File | Purpose |
|------|---------|
| `NotesOverlay.py` | Main Python plugin (MinorMode) |
| `notes_dialog.mu` | Custom Qt dialog for text input |
| `clipboard.mu` | Clipboard access via Qt's QClipboard |
| `PACKAGE` | RV package manifest |
| `NotesOverlay.rvpkg` | Installable package (zip of above) |

## Testing

1. Symlink files to RV plugin directories:
   ```bash
   # macOS
   ln -s /path/to/NotesOverlay.py ~/Library/Application\ Support/RV/Python/
   ln -s /path/to/notes_dialog.mu ~/Library/Application\ Support/RV/Mu/
   ```

2. Restart RV after changes

3. Test via `Review > Add Note` menu or `Shift+N` hotkey
