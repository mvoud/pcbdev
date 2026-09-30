# PCBDEV

**Generate KiCad symbols and footprints from a JSON file.**

[![Latest Release](https://img.shields.io/github/v/release/mvoud/pcbdev?style=flat-square)](https://github.com/mvoud/pcbdev/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey?style=flat-square)]()

---

## Why PCBDEV?

Many development board manufacturers — Waveshare, DFRobot, M5Stack — **do not provide official KiCad libraries**. Creating them by hand takes hours of tedious work in the KiCad editors, and it's error-prone.

**PCBDEV solves this.** Define your board once in a simple JSON file, and get:

- ✅ A KiCad **symbol** with proper pin types and geometry
- ✅ One or more **footprint** variants (THT, SMD, castellated)
- ✅ Automatic **symbol ↔ footprint association**
- ✅ Files **automatically copied** into your KiCad libraries

All in **one command**.

---

## Quick example

Define your board:

```json
{
  "board": {
    "name": "MyBoard",
    "dimensions": { "width": 30.0, "height": 20.0 },
    "symbol": { "body_width": 25.4 },
    "footprints": [
      {
        "name": "MyBoard_THT",
        "type": "tht_dual_row",
        "pitch_y": 2.54,
        "offset_x": 10.16,
        "pad_diameter": 1.8,
        "drill": 1.0
      }
    ],
    "pins": [
      { "number": 1, "name": "VCC", "type": "power_in", "side": "left" },
      { "number": 2, "name": "GND", "type": "power_in", "side": "left" },
      { "number": 3, "name": "TX",  "type": "output",   "side": "right" },
      { "number": 4, "name": "RX",  "type": "input",    "side": "right" }
    ]
  }
}