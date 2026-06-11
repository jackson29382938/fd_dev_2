# FTID Generator - Deployment Checklist

## Pre-Build Checklist

### 1. Install All Dependencies
```bash
pip install -r requirements.txt
```

Key dependencies for PDF generation:
- `img2pdf` - Primary PDF generation (most reliable)
- `Pillow` - Fallback PDF generation & image processing
- `pandas` - Excel/CSV import
- `openpyxl` - Excel file handling

### 2. Test Locally First
Run the application locally to ensure all features work:
```bash
python main.py
```

Test these critical features:
- [ ] Option 4: FTID UPS generation
- [ ] Option 5: FTID USPS generation  
- [ ] Option 6: FTID FEDEX generation
- [ ] Option 8: Excel/CSV import with PDF generation
- [ ] Verify PDF is created in Downloads folder
- [ ] Check that blank templates are used (not full)

## Building the Executable

### 3. Run Build Script
```bash
python build_app.py
```

Select your target platform:
1. macOS ARM (Apple Silicon - M1, M2, M3, etc.)
2. macOS Intel (x86_64)
3. Windows (x64)
4. Build All (current platform variations)

### 4. What Gets Included

**Bundled Directories:**
- `ftid_gen/` - Core generation logic
- `user_tracking/` - Subscription & tracking
- `requirements/` - Required data files (fonts, etc.)
- `maxicode/` - Maxicode handling
- `barcodes/` - Barcode generation
- `complete/` - Output directory
- `progress/` - Temporary files

**Bundled Files:**
- `ftid_data.json` - User data storage
- `ftid_settings.json` - Settings
- `previous_maxicode.json` - Maxicode history
- `.encryption.key` - Encryption key

**Hidden Imports (automatically included):**
- `img2pdf` - PDF generation
- `PIL.Image`, `PIL.PngImagePlugin` - Image processing
- `pandas`, `openpyxl` - Excel handling
- `gspread`, `oauth2client` - Google Sheets
- `barcode`, `zint` - Barcode libraries
- All other dependencies from requirements.txt

## Post-Build Testing

### 5. Test the Executable

**On the same machine:**
```bash
# Navigate to the dist folder
cd dist/ftid_generator_mac-arm/

# Run the executable
./ftid_generator
```

**Test checklist:**
- [ ] Application starts without errors
- [ ] Can generate labels (options 4, 5, 6)
- [ ] Excel import works (option 8)
- [ ] PDF is generated successfully
- [ ] PDF opens correctly and shows all labels
- [ ] No overlapping images in PDF

### 6. Test on a Clean Machine

**Important:** Test on a computer that doesn't have Python or your dev environment.

**What to provide to testers:**
1. The `.zip` file from `dist/` folder
2. Instructions to extract and run
3. Note about security warnings (see below)

## Distribution Notes

### macOS Users
1. Extract the .zip file
2. Right-click the executable → "Open" (first time only)
3. If blocked: System Settings → Privacy & Security → Allow
4. Run `chmod +x ftid_generator` if permission denied

### Windows Users
1. Extract the .zip file
2. Right-click the .exe → "Run as administrator" (first time)
3. If Windows Defender blocks: Click "More info" → "Run anyway"
4. Some antivirus may flag it (false positive) - whitelist if needed

## Common Issues & Solutions

### Issue: "img2pdf module not found"
**Solution:** The executable should bundle img2pdf. If users see this:
- They're likely running the .py file directly instead of the executable
- Rebuild with updated build_app.py (img2pdf in hiddenimports)

### Issue: PDF shows overlapping images
**Solution:** Fixed - now uses blank templates instead of full templates
- Verify in `label_processor.py` line 98: returns `blank_output_path`

### Issue: Excel import shows "NAN" for addresses
**Solution:** Fixed - empty Excel cells now trigger address generation
- Verify in `excel_importer.py` lines 269-271: checks for 'nan' string

### Issue: Can't find previous Excel files (option 3)
**Solution:** File history is stored in `ftid_data.json`
- Ensure `ftid_data.json` is in the same directory as executable
- History is automatically saved when using options 1 or 2

## Auto-Install Feature

The application has auto-install for missing dependencies:
```python
REQUIRED_MODULES = {
    "requests": "requests",
    "pydash": "pydash",
    "PIL": "Pillow",
    "barcode": "python-barcode",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "img2pdf": "img2pdf"  # ← Critical for PDF
}
```

**Note:** Auto-install only works if:
- User has pip installed
- Internet connection available
- User has write permissions

**For executables:** All modules are pre-bundled, so auto-install shouldn't trigger.

## File Structure for Deployment

```
ftid_generator_mac-arm.zip
└── ftid_generator_mac-arm/
    ├── ftid_generator          # ← Executable
    ├── ftid_gen/               # Bundled
    ├── user_tracking/          # Bundled
    ├── requirements/           # Bundled
    ├── maxicode/               # Bundled
    ├── barcodes/               # Bundled
    ├── complete/               # Bundled (empty)
    ├── progress/               # Bundled (empty)
    ├── ftid_data.json          # Bundled
    ├── ftid_settings.json      # Bundled
    ├── previous_maxicode.json  # Bundled
    └── .encryption.key         # Bundled
```

## Final Verification

Before distributing:
- [ ] Tested all main features in executable
- [ ] PDF generation works (check Downloads folder)
- [ ] Blank templates used (no overlapping)
- [ ] Excel import handles empty cells
- [ ] Previous file reuse works (option 3)
- [ ] Tested on clean machine (no Python installed)
- [ ] Created user documentation/README
- [ ] Verified file size is reasonable (~50-200MB typical)

## Rollout Strategy

1. **Alpha Test:** Your machine only
2. **Beta Test:** 2-3 trusted users with different machines
3. **Release:** Broader distribution
4. **Support:** Monitor for issues, collect feedback

## Version Control

Current version includes:
- ✅ Excel import with real Yelp addresses
- ✅ Reuse previous Excel files (option 3)
- ✅ Combined PDF generation (Downloads folder)
- ✅ Blank templates (no overlapping)
- ✅ NAN address fix
- ✅ img2pdf integration

Update version number in your app before each major release.
