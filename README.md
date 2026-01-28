# NotesOverlay for OpenRV

📝 A Python plugin for [OpenRV](https://github.com/AcademySoftwareFoundation/OpenRV) that adds text annotation overlays to your review sessions.

## ✨ Features

### Quick Notes
- Add notes via `Review > Add Note` menu or `Shift+N` hotkey

![notesOverlay_RV_05](https://github.com/user-attachments/assets/b7e44b26-5fe6-42cd-982d-c577a413466c)

- Multi-line text input with copy/paste support

![notesOverlay_RV_01b](https://github.com/user-attachments/assets/65763889-0a46-4006-a9c0-69748a077df8)

![notesOverlay_RV_02b](https://github.com/user-attachments/assets/6d921c27-d68e-4cc3-bec1-f45059f87e04)

- White text with black outline for readability on any background
![notesOverlay_RV_04](https://github.com/user-attachments/assets/c368e99c-85da-4008-a0e2-3f5da485fe94)

- Smart text wrapping and vertical stacking
![notesOverlay_RV_03](https://github.com/user-attachments/assets/08ddba45-fce2-41de-b3c9-b8323d1aee59)

- Notes persist in session files (survives save/autosave)


### Copy to Clipboard (New in v1.3.0)
- Export all notes with `Cmd+Shift+C` (macOS) / `Ctrl+Shift+C`
- Markdown-friendly format with header, body, and file path
- Captures both plugin notes AND RV's native paint annotations
- Drawing-only frames show placeholder


Example Note result:
```
Notes on pexels-rodnae-productions-8474580.mp4
2026-01-28 08:20

---

Frame 1
- *see annotated frame

Frame 18
- some really long note about how i went ot the moon and we might want to check a bunch of stuff
- just to test, a new note as well

Frame 29
- note here

Frame 63
- note 1
- another note 2
- more note

Frame 133
- WOW look at this here

Frame 194
- *see annotated frame

Frame 257
- random note to do on this frame

---

/Users/somebody/Downloads/pexels-rodnae-productions-8474580.mp4
```


### Keyboard Shortcuts
| Action | Shortcut |
|--------|----------|
| Add Note | `Shift+N` |
| Copy Notes | `Cmd+Shift+C` / `Ctrl+Shift+C` |
| Submit Note | `Enter` |
| New Line | `Shift+Enter` |
| Cancel | `Escape` |


## 🚀 Installation

### Quick Install (recommended)

1. Download the latest `.rvpkg` from this repository
2. In RV: `Preferences > Packages > Add Package...`
3. Select the downloaded `.rvpkg` file
4. Restart RV

### Development (symlink)

```bash
# macOS
ln -s /path/to/NotesOverlay.py ~/Library/Application\ Support/RV/Python/
ln -s /path/to/notes_dialog.mu ~/Library/Application\ Support/RV/Mu/
ln -s /path/to/clipboard.mu ~/Library/Application\ Support/RV/Mu/

# Linux
ln -s /path/to/NotesOverlay.py ~/.rv/Python/
ln -s /path/to/notes_dialog.mu ~/.rv/Mu/
ln -s /path/to/clipboard.mu ~/.rv/Mu/
```

### Build from Source

```bash
zip -r NotesOverlay.rvpkg PACKAGE NotesOverlay.py notes_dialog.mu clipboard.mu
```

## 📖 Usage

### Adding Notes

1. Navigate to the frame you want to annotate
2. Press `Shift+N` or use `Review > Add Note`
3. Type your note in the dialog (multi-line supported, copy/paste works)
4. Press `Enter` to save, `Escape` to cancel (`Shift+Enter` for new line)

Notes appear in the top-left of the image with a bullet point prefix. The dialog title shows the source frame number for reference.

### Exporting Notes

Press `Cmd+Shift+C` (macOS) or `Ctrl+Shift+C` to copy all notes to clipboard:

```
Notes on shot_010_v002.mov
2026-01-28 14:30

---

Frame 1001
- First note on this frame
- Second note

Frame 1045
- Another observation

---

/path/to/shot_010_v002.mov
```

The export includes both plugin notes and RV's native annotations. Frames with only drawings show `- *see annotated frame` as a placeholder.

## ⚙️ Configuration

Text rendering can be customized by modifying constants in `NotesOverlay.py`:

```python
TEXT_SIZE = 0.005           # Text size (% of image height)
MAX_CHARS_PER_LINE = 58     # Characters before wrapping
LINE_SPACING = 0.08         # Space between stacked notes
```

## 📚 About OpenRV

Open RV is the open-source version of RV, the Sci-Tech award–winning media review and playback software from the Academy Software Foundation.

- **Source:** [AcademySoftwareFoundation/OpenRV](https://github.com/AcademySoftwareFoundation/OpenRV)
- **Documentation:** [Open RV Docs](https://aswf-openrv.readthedocs.io/)
- **Package format:** [RV Reference Manual - Chapter 10](https://aswf-openrv.readthedocs.io/en/latest/rv-manuals/rv-reference-manual/rv-reference-manual-chapter-ten.html)

## 📄 License

See [LICENSE](LICENSE) if present.

Video by RDNE Stock project: https://www.pexels.com/video/overhead-shot-of-astronauts-walking-in-an-outdoor-area-8474580/
