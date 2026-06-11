# FTID Generator - Build Instructions

## Quick Start

```bash
python build_app.py
```

Select your target platform:
1. macOS ARM (Apple Silicon)
2. macOS Intel
3. Windows
4. Build All

## Requirements

- Python 3.8+
- All dependencies from `requirements.txt`
- PyInstaller (auto-installed)

## Output

Built apps are in `dist/` folder:
- macOS: `FTID_Generator.app` bundle
- Windows: `FTID_Generator.exe`
- ZIP archives for distribution

## Platform Notes

### macOS
- Build on Mac for Mac apps
- First run: Right-click > Open (bypass Gatekeeper)

### Windows  
- Build on Windows for Windows apps
- May need "Run anyway" on first launch

## Troubleshooting

**Build fails**: Reinstall dependencies
```bash
pip install -r requirements.txt --force-reinstall
```

**"App is damaged" on macOS**: Remove quarantine
```bash
xattr -cr dist/FTID_Generator_*/FTID_Generator.app
```
