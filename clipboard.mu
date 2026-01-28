//
// NotesOverlay - Clipboard Utilities
// ===================================
// Provides clipboard access via Qt for the NotesOverlay plugin.
//
// This module uses RV's Mu Qt bindings to access the system clipboard.
// It's called from Python via rv.runtime.eval() to copy text.
//
// USAGE FROM PYTHON:
// ------------------
// rv.runtime.eval('require clipboard; clipboard.copyText("text here");', [])
//

module: clipboard {

use qt;

// Module-level storage for text to copy (workaround for complex strings)
string _pendingText;

//
// Set text to be copied (called first, handles complex strings)
//
\: setPendingText (void; string text)
{
    _pendingText = text;
}

//
// Copy the pending text to clipboard
//
\: copyPending (void;)
{
    QClipboard clip = QApplication.clipboard();
    clip.setText(_pendingText);
}

//
// Copy text directly to system clipboard
//
// Args:
//     text: The string to copy to clipboard
//
\: copyText (void; string text)
{
    QClipboard clip = QApplication.clipboard();
    clip.setText(text);
}

} // end module clipboard
