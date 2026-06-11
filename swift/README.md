# FTIDMacApp — Swift (macOS) build

A native macOS front-end for the FTID label generator, written in SwiftUI. The
app is driven by a small Python "bridge" that lives in `vendor/backend/` so the
swift folder is **fully self-contained** — it can be moved, copied, or built
without touching the sibling `python/` project.

```
swift/
├── Package.swift              Swift Package Manager manifest
├── Sources/FTIDMacApp/        SwiftUI source
├── script/
│   ├── build_and_run.sh       Build the .app bundle, code-sign, launch
│   ├── install_python_deps.sh Populate vendor/python-site-packages
│   ├── sync_from_python.sh    Refresh vendor/backend from ../python (optional)
│   └── build_windows.ps1      Windows packaging helper (no-op on macOS)
├── vendor/
│   ├── app_icon.icns          App icon (vendored from python/requirements/)
│   ├── backend/               Python bridge + backend the Swift app drives
│   │   ├── bridge/ftid_bridge.py
│   │   ├── ftid_gen/          Address, tracking, label, settings, maxicode
│   │   ├── user_tracking/     Subscription / run-history
│   │   ├── maxicode/          MaxiCode encoder + Java helpers
│   │   ├── requirements/      Fonts, icons, helper resources
│   │   ├── .env               (optional) embedded config
│   │   └── .encryption.key    (optional) embedded key
│   └── python-site-packages/  Populated by install_python_deps.sh
├── dist/                      Built .app bundle (created by build_and_run.sh)
└── README.md                  This file
```

## Prerequisites

* macOS 14 (Sonoma) or newer
* Xcode 15+ or the Swift 5.9+ command-line toolchain (`swift --version`)
* Python 3.13 from [python.org](https://www.python.org/downloads/) — the app
  bundles `/Library/Frameworks/Python.framework`
  * Override with `FTID_PYTHON_FRAMEWORK=/path/to/Python.framework` if you
    keep Python somewhere else

## First-time setup

```bash
cd swift
bash script/install_python_deps.sh       # one-time: fill vendor/python-site-packages
```

That script resolves a Python 3.13 interpreter (override with `PYTHON_BIN=...`)
and installs everything from `vendor/backend/requirements/requirements.txt`
into `vendor/python-site-packages/`. Re-run it any time the Python requirements
change.

If you only want to verify the destination exists without re-installing, set
`SKIP_INSTALL=1`.

## Build & run

```bash
cd swift
bash script/build_and_run.sh            # build, code-sign, and launch
```

Useful flags:

| Flag              | What it does                                                  |
| ----------------- | ------------------------------------------------------------- |
| `run` (default)   | Build, code-sign, then `open` the .app                        |
| `--build-only`    | Stage the .app bundle under `dist/FTIDMacApp.app` and stop    |
| `--debug`         | Open the binary in `lldb` after staging                       |
| `--logs`          | Launch the app and stream `log stream` filtered to the process|
| `--telemetry`     | Launch and stream subsystem logs only                         |
| `--verify`        | Launch, sleep 2s, then assert the process is still running    |

## Updating the vendored Python backend (optional)

The `swift/` folder does not need `python/` to build. If you do want to pull
the latest backend in from the sibling Python project, run:

```bash
cd swift
bash script/sync_from_python.sh                 # uses ../python by default
bash script/sync_from_python.sh /path/to/python # custom location
```

This mirrors `bridge/`, `ftid_gen/`, `user_tracking/`, `maxicode/`,
`requirements/`, `.env`, `.encryption.key`, and `app_icon.icns` from the
Python project into `vendor/`. After syncing, re-run
`install_python_deps.sh` only if the requirements changed.

## Environment overrides

| Variable                | Default                                            | Purpose                                            |
| ----------------------- | -------------------------------------------------- | -------------------------------------------------- |
| `FTID_PYTHON_FRAMEWORK` | `/Library/Frameworks/Python.framework`             | Path to the Python 3.13 framework to bundle        |
| `FTID_PYTHON_SITE_PACKAGES` | *(unset)*                                      | Hard override for the site-packages directory      |
| `PYTHON_BIN`            | `/Library/Frameworks/.../bin/python3.13`           | Used by `install_python_deps.sh`                   |
| `PIP_INDEX_URL`         | PyPI                                               | Custom index for `install_python_deps.sh`          |

## What gets bundled into the .app

`build_and_run.sh` produces `dist/FTIDMacApp.app` with:

```
FTIDMacApp.app/Contents/
├── MacOS/FTIDMacApp                  Swift-compiled executable
├── Frameworks/Python.framework/…     Python 3.13 runtime
├── Resources/
│   ├── AppIcon.icns                  App icon (from vendor/)
│   ├── python-site-packages/…        Vendored third-party deps
│   └── backend/                      Mirror of vendor/backend/...
└── Info.plist                        Generated by the build script
```

## Cleaning up build artefacts

```bash
rm -rf swift/.build swift/dist
```

This is safe; both are pure build output and will be regenerated on the next
`build_and_run.sh` run.
