# FTID Generator — Python (cross-platform) build

A cross-platform Python implementation of the FTID label generator. Uses
`customtkinter` for a native-looking dark-mode GUI on macOS / Windows, and a
plain `print`/`input` flow as the terminal fallback. This folder is **fully
self-contained** — it can be moved, copied, or built without the sibling
`swift/` project.

```
python/
├── main.py                 Terminal (CLI) entry point
├── gui_app.py              CustomTkinter GUI entry point
├── run_gui.command         macOS Finder launcher
├── build_app.py            PyInstaller build script (mac + windows)
├── requirements.txt        Python package dependencies
├── *.spec                  Pre-baked PyInstaller spec files (mac/intel/arm/gui)
├── ftid_gen/               Label generation, addresses, settings, maxicode
│   ├── address_utils.py
│   ├── excel_importer.py
│   ├── ftid_generator.py
│   ├── label_processor.py
│   ├── settings_manager.py
│   ├── settings_menu.py
│   ├── enhanced_maxicode.py
│   ├── previous_maxicode.py
│   ├── core/ render/ complete/ progress/ templates/
│   └── …
├── user_tracking/          Subscription manager + CSV / Drive logging
│   ├── subscription_manager.py
│   ├── csv_manager.py
│   └── google_drive_logger.py
├── bridge/ftid_bridge.py   JSON bridge used by the macOS Swift app
├── maxicode/               MaxiCode encoder + Java helpers
│   ├── decode_maxicode.py
│   ├── assets/
│   └── jar-files/
├── requirements/           Static resources used by the label pipeline
│   ├── ARIAL.TTF, BabelSans*.ttf, NotoSans*.ttf
│   ├── app_icon.icns
│   ├── halal.png, halal_icon.png, halal.iconset/
│   ├── label_history.csv
│   ├── zipcodes.json
│   ├── credentials.json
│   ├── zint.exe / libzint.dll        (Windows-only)
│   └── requirements.txt
├── barcodes/ complete/ progress/  Output folders
├── tests/                  pytest-style tests
├── .env .encryption.key ftid_data.json ftid_settings.json previous_maxicode.json
└── README.md               This file
```

## Prerequisites

* Python **3.10+** (3.13 recommended)
* Tkinter (built in on python.org / Windows installers; on Homebrew install
  `brew install python-tk@3.13`)
* pip

## Install dependencies

```bash
cd python
python3 -m pip install -r requirements.txt
```

## Run the GUI

### macOS (easiest)

Double-click `run_gui.command` in Finder, or:

```bash
cd python
./run_gui.command
```

`run_gui.command` prefers Python 3.13 from python.org
(`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13`) because
the Homebrew build often lacks Tkinter, then falls back to `python3` on PATH.

### macOS / Windows / Linux (manual)

```bash
cd python
python3 gui_app.py
```

## Run the terminal app

```bash
cd python
python3 main.py
```

## Run the tests

```bash
cd python
python3 -m pytest tests
```

## Build standalone executables

```bash
cd python
python3 build_app.py                       # interactive menu
# or
python3 build_app.py --target mac-arm --gui          # GUI, Apple Silicon
python3 build_app.py --target mac-intel --gui        # GUI, Intel
python3 build_app.py --target windows --gui          # GUI, Windows
python3 build_app.py --target mac-arm                # terminal, Apple Silicon
```

`build_app.py` uses PyInstaller to package the entire app (including the
`ftid_gen/`, `user_tracking/`, `bridge/`, `maxicode/`, `requirements/`,
`barcodes/`, `complete/`, `progress/` directories plus `ftid_data.json`,
`ftid_settings.json`, `previous_maxicode.json`, `.env`, `.encryption.key`)
into a single redistributable bundle under `dist/`. The pre-baked
`FTID_Generator*.spec` files are equivalent to what the script would
generate — keep them if you want to build with `pyinstaller <spec>` directly.

## State / config files

These live at the root of `python/` and are read/written at runtime:

* `.env` — environment variables (loaded by `python-dotenv`)
* `.encryption.key` — symmetric key used by parts of the subscription flow
* `ftid_data.json` — small persistent data store
* `ftid_settings.json` — UI / behaviour settings
* `previous_maxicode.json` — last-used MaxiCode state

If you copy this folder to a new machine, copy these files along with it.

## Output folders

The app writes to:

* `python/barcodes/` — generated PNG labels
* `python/complete/` — completed batch artefacts
* `python/progress/` — per-job progress snapshots
* `python/user_tracking/label_history.csv` — run history

If you want a clean slate, delete the contents of these folders (do **not**
delete the folders themselves).

## Cleaning build artefacts

```bash
rm -rf python/build python/dist
```

These are produced by `build_app.py` and are safe to delete.
