# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-27

### ✨ Added

- **NotesOverlay plugin** — Text annotation overlay for OpenRV
  - `Review > Add Note` menu item with `Shift+N` hotkey
  - Native RV text entry mode (Mu-based, no external dependencies)
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
- Pre-built `NotesOverlay-1.0.rvpkg` ready for download
- Documentation and changelog structure
