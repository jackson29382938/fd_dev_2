# 🔧 FTID Generator - Build Guide

Complete step-by-step guide for building standalone apps on any platform.

---

## 🍎 macOS (ARM M1/M2/M3)

```bash
# 1. Install Python 3.13 from python.org (Universal installer)
# Download: https://www.python.org/downloads/macos/
# Choose: "macOS 64-bit universal2 installer"

# 2. Navigate to project folder
cd ~/Desktop/ftid_project

# 3. Create virtual environment using python.org Python
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -m venv venv_build

# 4. Install ALL requirements (use PIP_USER=0 to avoid --user error)
PIP_USER=0 ./venv_build/bin/pip install --upgrade pip
PIP_USER=0 ./venv_build/bin/pip install pyinstaller customtkinter pillow pandas numpy requests openpyxl pydash python-barcode python-dotenv gspread oauth2client pyobjc-framework-Cocoa pyperclipimg python-Levenshtein xlrd google-api-python-client

# 5. Build standalone app with icon
./venv_build/bin/python -m PyInstaller --onedir --windowed \
  --name "FTID_Generator" \
  --icon "requirements/app_icon.icns" \
  --add-data "ftid_gen:ftid_gen" \
  --add-data "maxicode:maxicode" \
  --add-data "requirements:requirements" \
  --add-data "user_tracking:user_tracking" \
  --hidden-import customtkinter --hidden-import PIL --hidden-import tkinter \
  --hidden-import gspread --hidden-import oauth2client \
  --clean --noconfirm gui_app.py

# 6. Create ZIP for distribution
cd dist && zip -r FTID_Generator_macOS_ARM.zip FTID_Generator.app
```

---

## 🍎 macOS (Intel x86_64)

```bash
# Same as ARM, but on an Intel Mac
# The steps are IDENTICAL - Python will build for the native architecture

# 1. Install Python 3.13 from python.org
# 2. Create venv
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 -m venv venv_build

# 3. Install requirements
PIP_USER=0 ./venv_build/bin/pip install --upgrade pip
PIP_USER=0 ./venv_build/bin/pip install pyinstaller customtkinter pillow pandas numpy requests openpyxl pydash python-barcode python-dotenv gspread oauth2client pyobjc-framework-Cocoa pyperclipimg python-Levenshtein xlrd google-api-python-client

# 4. Build (SAME command)
./venv_build/bin/python -m PyInstaller --onedir --windowed \
  --name "FTID_Generator" \
  --icon "requirements/app_icon.icns" \
  --add-data "ftid_gen:ftid_gen" \
  --add-data "maxicode:maxicode" \
  --add-data "requirements:requirements" \
  --add-data "user_tracking:user_tracking" \
  --hidden-import customtkinter --hidden-import PIL --hidden-import tkinter \
  --hidden-import gspread --hidden-import oauth2client \
  --clean --noconfirm gui_app.py

# 5. Create ZIP
cd dist && zip -r FTID_Generator_macOS_Intel.zip FTID_Generator.app
```

---

## 🪟 Windows

```powershell
# 1. Install Python 3.13 from python.org
# Download: https://www.python.org/downloads/windows/
# ⚠️ IMPORTANT: CHECK "Add Python to PATH" during install!

# 2. Open PowerShell as Administrator, navigate to project
cd C:\Users\YourName\Desktop\ftid_project

# 3. Create virtual environment
python -m venv venv_build

# 4. Activate venv
.\venv_build\Scripts\Activate.ps1

# 5. Install ALL requirements
pip install --upgrade pip
pip install pyinstaller customtkinter pillow pandas numpy requests openpyxl pydash python-barcode python-dotenv gspread oauth2client python-Levenshtein xlrd google-api-python-client

# 6. Build standalone EXE (note: semicolons instead of colons for Windows paths)
python -m PyInstaller --onedir --windowed `
  --name "FTID_Generator" `
  --icon "requirements/halal_icon.png" `
  --add-data "ftid_gen;ftid_gen" `
  --add-data "maxicode;maxicode" `
  --add-data "requirements;requirements" `
  --add-data "user_tracking;user_tracking" `
  --hidden-import customtkinter --hidden-import PIL --hidden-import tkinter `
  --hidden-import gspread --hidden-import oauth2client `
  --clean --noconfirm gui_app.py

# 7. Create ZIP for distribution
Compress-Archive -Path dist\FTID_Generator -DestinationPath dist\FTID_Generator_Windows.zip
```

---

## 📋 Quick Reference

| Platform | Path Separator | Result | Icon |
|----------|---------------|--------|------|
| macOS ARM | `:` | `.app` bundle | ✅ halal.png |
| macOS Intel | `:` | `.app` bundle | ✅ halal.png |
| Windows | `;` | `.exe` folder | ✅ halal.png |

---

## 🔑 Key Differences Summary

| Item | macOS | Windows |
|------|-------|---------|
| **--add-data** | `source:dest` | `source;dest` |
| **Activate venv** | Built-in (no activate needed) | `.\venv\Scripts\Activate.ps1` |
| **PyObjC** | Required | Not needed |
| **Output** | `FTID_Generator.app` | `FTID_Generator.exe` |

---

## 📦 Required Project Files

Make sure these exist before building:
```
ftid_project/
├── gui_app.py          # Main GUI entry point
├── main.py             # Terminal entry point
├── ftid_gen/           # Core label generation
├── maxicode/           # MaxiCode generation
├── user_tracking/      # Subscription/login system
├── requirements/
│   ├── halal.png       # App icon
│   ├── zipcodes.json
│   ├── ARIAL.ttf
│   └── NotoSans-*.ttf
└── requirements.txt
```

---

## 🚀 Test Before Distributing

```bash
# macOS
open dist/FTID_Generator.app

# Windows
.\dist\FTID_Generator\FTID_Generator.exe
```

---

## 📤 Distribution

After building, share the ZIP file:
- `FTID_Generator_macOS_ARM.zip` → For M1/M2/M3 Macs
- `FTID_Generator_macOS_Intel.zip` → For older Intel Macs
- `FTID_Generator_Windows.zip` → For Windows PCs

Recipients just unzip and run!
