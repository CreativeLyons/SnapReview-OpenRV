//
// SnapReview - Custom Note Input Dialog
// ========================================
// Multi-line note input with full copy/paste support for OpenRV.
//
// This module creates a Qt-based dialog using RV's Mu Qt bindings.
// It provides a proper text editor (QTextEdit) instead of RV's limited
// native text entry mode.
//
// KEY LEARNINGS FOR RV MU DEVELOPMENT:
// ------------------------------------
// 1. QPushButton.clicked signal passes a `bool checked` parameter.
//    Callbacks MUST have signature: (void; bool checked)
//    NOT: (void;) - this will cause silent failures!
//
// 2. Closures don't work in Mu callbacks. You cannot reference local
//    variables from the enclosing function scope. Use module-level
//    globals instead.
//
// 3. Widget constructors vary:
//    - QLabel(text, parent, flags) - requires all 3 args
//    - QPushButton(text, parent) - 2 args
//    - QTextEdit(parent) - 1 arg
//    - QVBoxLayout(parent) or QVBoxLayout() - optional parent
//    - QHBoxLayout() - no args, use addLayout to add to parent
//
// 4. Use sendInternalEvent() to communicate back to Python code.
//    Python binds the event name in MinorMode.__init__().
//
// 5. QDialog.exec() returns 1 for Accepted, 0 for Rejected.
//
// 6. connect(widget, Signal.name, callbackFunction) - 3 args only.
//    The callback must be a named function, not an inline lambda
//    that references outer scope variables.
//
// 7. QShortcut/QKeySequence may not be available in Mu's Qt bindings.
//    Stick with buttons for reliable cross-platform behavior.
//
// 8. Subclassing QDialog to override keyPressEvent:
//    - Use `class: ClassName : ParentClass { ... }` syntax
//    - Constructor calls parent via `QDialog.QDialog(this, parent)`
//    - Override methods with `method: methodName (returnType; params) { ... }`
//    - Call parent method via `QDialog.keyPressEvent(this, event)`
//
// 9. Subclassing QTextEdit to override keyPressEvent:
//    - keyPressEvent receives QKeyEvent directly (no casting needed)
//    - IMPORTANT: Store parent dialog as class member variable
//    - Module-level globals can't be accessed from class methods
//    - Call parent method via QTextEdit.keyPressEvent(this, event)
//
// 10. Key constants: Qt.Key_Return (main Enter), Qt.Key_Enter (numpad)
//     Modifier check: (event.modifiers() & Qt.ShiftModifier) != 0
//

module: notes_dialog {

use qt;
use commands;
use extra_commands;

// -----------------------------------------------------------------------------
// NoteTextEdit - Custom QTextEdit with Slack-style Enter behavior
// -----------------------------------------------------------------------------
// Subclasses QTextEdit to override keyPressEvent:
// - Enter (without Shift) = submit dialog
// - Shift+Enter = insert newline (default behavior)
// - Ctrl+Enter = also submit (backup shortcut)

class: NoteTextEdit : QTextEdit
{
    // Store reference to parent dialog for accept() call
    QDialog _parentDialog;

    // Constructor - initialize parent QTextEdit and store dialog reference
    method: NoteTextEdit (NoteTextEdit; QDialog dialog)
    {
        QTextEdit.QTextEdit(this, dialog);
        _parentDialog = dialog;
    }

    // Override keyPressEvent to intercept Enter key
    method: keyPressEvent (void; QKeyEvent event)
    {
        int key = event.key();
        int mods = event.modifiers();

        // Check for Enter/Return key
        if (key == Qt.Key_Return || key == Qt.Key_Enter)
        {
            // Shift+Enter = let through for newline
            if ((mods & Qt.ShiftModifier) != 0)
            {
                QTextEdit.keyPressEvent(this, event);
                return;
            }

            // Enter on empty text = cancel (same as Escape)
            string text = toPlainText();
            if (text == "")
            {
                _parentDialog.reject();
                return;
            }

            // Enter with text = submit dialog
            _parentDialog.accept();
            return;
        }

        // All other keys: pass to parent
        QTextEdit.keyPressEvent(this, event);
    }
}

// Global references for callbacks (required - closures don't work in Mu)
QDialog _dlg;
NoteTextEdit _txt;

// Module-level function to accept dialog (callable from event filter)
\: acceptDialog (void;) { _dlg.accept(); }

// Callback for Add Note button
// NOTE: Must accept `bool checked` parameter from QPushButton.clicked signal!
\: doAccept (void; bool checked) { _dlg.accept(); }

// Callback for Cancel button
\: doReject (void; bool checked) { _dlg.reject(); }

// Main entry point - called from Python via rv.runtime.eval()
\: showNoteDialog (void;)
{
    // Get RV's main window as parent for proper window management
    QWidget parent = mainWindowWidget();

    // Create modal dialog
    // NOTE: setWindowFlags() crashes RV - don't use Qt.Tool, Qt.Popup, or Qt.FramelessWindowHint
    _dlg = QDialog(parent);
    int srcFrame = sourceFrame(frame());
    _dlg.setWindowTitle("Add Note @ Frame %d" % srcFrame);

    // Minimal size - just the text input
    _dlg.resize(500, 55);

    // Minimal margins for terminal-like feel
    QVBoxLayout layout = QVBoxLayout(_dlg);
    layout.setContentsMargins(4, 4, 4, 4);
    layout.setSpacing(0);

    // Multi-line text editor with Slack-style Enter behavior
    // Uses custom NoteTextEdit subclass that overrides keyPressEvent
    _txt = NoteTextEdit(_dlg);
    _txt.setAcceptRichText(false);  // Strip formatting on paste
    _txt.setFixedHeight(45);        // ~2 lines of text
    _txt.setPlaceholderText("Enter to add, Shift+Enter for new line, Esc to cancel");
    layout.addWidget(_txt);

    // No buttons - Enter submits, Escape cancels

    // Position dialog: bottom of parent window, horizontally centered
    // Use frameGeometry to include window decorations
    QRect parentGeo = parent.frameGeometry();
    int dialogHeight = _dlg.sizeHint().height();
    int dialogX = parentGeo.x() + (parentGeo.width() - 500) / 2;
    int dialogY = parentGeo.y() + parentGeo.height() - dialogHeight - 100;
    _dlg.move(dialogX, dialogY);

    // Show dialog and wait for result
    // Returns 1 (QDialog.Accepted) or 0 (QDialog.Rejected)
    int result = _dlg.exec();

    // Only send text if dialog was accepted (Enter pressed)
    if (result == 1)
    {
        string text = _txt.toPlainText();
        if (text != "")
        {
            // Send event to Python handler
            sendInternalEvent("notes-overlay-text-entered", text, "");
        }
    }
}

} // end module notes_dialog
