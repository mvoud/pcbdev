# pcbdev

> Build easily your own PCB libraries with a JSON-based language.
> Starting from a pinout reference, generate KiCad symbols and footprints automatically.

## ✨ Features

- 📝 Define your board once in a simple `layout.json`
- 🔧 Generate multiple footprint variants (THT, SMD, castellated)
- 🎯 Create KiCad symbols with proper pin types and geometry
- 🔗 Automatic symbol ↔ footprint association
- 📦 Auto-copy generated files into your KiCad libraries
- 🔍 Auto-detect installed KiCad version
- 💻 Cross-platform CLI (Linux, macOS, Windows)

## 🚀 Quick Start

### Install

```bash
git clone git@github.com:mvoud/pcbdev.git
cd pcbdev
python command.py --init
python command.py --compile
