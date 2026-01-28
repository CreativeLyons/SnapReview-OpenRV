# NotesOverlay for OpenRV

📝 A Python plugin for [OpenRV](https://github.com/AcademySoftwareFoundation/OpenRV) that adds text annotation overlays to your review sessions.

## ✨ Features

- **Quick Notes** — Add notes via `Review > Add Note` menu or `Shift+N` hotkey
- **Copy to Clipboard** — Export all notes via `Cmd+Shift+C` (macOS) or `Ctrl+Shift+C`
- **Multi-line Input** — Full text editor dialog with copy/paste support (Cmd+C/V)
- **Clear Text** — White text with black outline readable on any background
- **Smart Wrapping** — Long text automatically wraps to fit within frame
- **Stacking** — Multiple notes per frame stack vertically
- **Multi-Source** — Works correctly with sequences containing multiple clips
- **Timeline Markers** — Frames with notes are automatically marked
- **Native Annotation Support** — Also captures RV's built-in paint/text annotations
- **Persistent** — Notes survive session save, autosave, and reload

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
