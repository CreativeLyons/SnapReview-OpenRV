# NotesOverlay for OpenRV

📝 A Python plugin for [OpenRV](https://github.com/AcademySoftwareFoundation/OpenRV) that adds text annotation overlays to your review sessions.

## ✨ Features

- **Quick Notes** — Add notes via `Review > Add Note` menu or `Shift+N` hotkey
- **Clear Text** — White text with black outline readable on any background
- **Smart Wrapping** — Long text automatically wraps to fit within frame
- **Stacking** — Multiple notes per frame stack vertically
- **Multi-Source** — Works correctly with sequences containing multiple clips
- **Timeline Markers** — Frames with notes are automatically marked
- **Persistent** — Notes survive session save, autosave, and reload

## 🚀 Installation

### Quick Install (recommended)

1. Download `NotesOverlay-1.0.rvpkg` from this repository
2. In RV: `Preferences > Packages > Add Package...`
3. Select the downloaded `.rvpkg` file
4. Restart RV

### Development (symlink)

```bash
# macOS
ln -s /path/to/NotesOverlay.py ~/Library/Application\ Support/RV/Python/

# Linux
ln -s /path/to/NotesOverlay.py ~/.rv/Python/
```

### Build from Source

```bash
zip -r NotesOverlay-1.0.rvpkg PACKAGE NotesOverlay.py
```

## 📖 Usage

1. Navigate to the frame you want to annotate
2. Press `Shift+N` or use `Review > Add Note`
3. Type your note in the prompt at the bottom of the screen
4. Press `Enter` to add the note

Notes appear in the top-left of the image with a bullet point prefix.

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
