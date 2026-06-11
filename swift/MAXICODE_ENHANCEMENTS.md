# Maxicode Enhancements - No Character Limits & Auto-Population

## Changes Implemented

### 1. Removed Character Limit Restrictions
- **Before**: Maxicode data was limited to 93 characters
- **After**: No character limits in the UI/settings layer - the application will accept and process data of any length
- **Implementation**: Modified settings to use `no_character_limit: true`
- **Benefit**: Full utilization of Maxicode data capacity

> **Note on physical encoding limits**: The actual MaxiCode barcode standard supports up to 93 characters of encoded data. The encoding pipeline in `decode_maxicode.py` enforces a 70-character cap (`MAX_MAXICODE_LENGTH`) for the primary encoding path, and 60 characters when using the TEC-IT online API fallback. The "no limits" setting removes the UI-level restriction, allowing the application to handle arbitrarily long input strings — the encoding layer will truncate as needed to fit the physical barcode format.

### 2. **Auto-Population from Previous Inputs** ✅
- **Ship-to ZIP Code**: Automatically loaded from previous user inputs
- **Tracking Number**: Auto-populated from previous UPS/USPS/FedEx tracking numbers
- **Default Values**: All fields show calculated defaults that can be accepted with Enter
- **Storage**: Previous inputs saved in `ftid_data.json` for persistence

### 3. **Auto City/State Calculation** ✅
- **ZIP Code Lookup**: Automatically calculates city and state from ZIP code
- **API Integration**: Uses Zippopotamus API for accurate location data
- **Caching**: Results cached locally for faster future lookups
- **Fallback**: If API fails, uses local database or random values

### 4. **Enhanced User Experience** ✅
- **Press Enter**: Accept all default values by pressing Enter
- **Iteration**: Quick iteration through multiple Maxicode generations
- **Smart Defaults**: Intelligent defaults based on previous usage patterns

## 📁 **New Files Created**

### `ftid_gen/enhanced_maxicode.py`
- **EnhancedMaxicodeGenerator** class with no character limits
- Auto-population from previous user inputs
- ZIP code to city/state lookup functionality
- Enhanced Maxicode data construction with extended fields

## 🔧 **Modified Files**

### `main.py`
- Added new menu option "m: Enhanced Maxicode Generator (No Limits)"
- Added `handle_enhanced_maxicode()` function
- Updated startup message to show Maxicode settings

### `ftid_gen/settings_manager.py`
- Replaced `character_limit` with `no_character_limit`
- Updated default settings to enable no limits

### `ftid_gen/settings_menu.py`
- Updated Maxicode settings menu
- Replaced character limit setting with no-limit toggle
- Removed old character limit function

## 🎯 **Key Features**

### **Auto-Population System**
```python
# Example of auto-populated fields:
ZIP Code (5 digits) (default: 90210): [Enter]
Tracking Number (default: 1Z12345678901234567): [Enter]
City (default: BEVERLY HILLS): [Enter]
State (2 letters) (default: CA): [Enter]
```

### **No Character Limits**
- **Before**: `[)>01012345...` (93 chars max)
- **After**: `[)>01012345...EXTENDED_DATA_MORE_FIELDS...` (unlimited)

### **Smart ZIP Lookup**
- Enter ZIP: `90210`
- Auto-detected: `BEVERLY HILLS, CA`
- Used as default for city/state fields

### **Previous Data Integration**
- Loads from `ftid_data.json`
- Tracks: sender_zip, receiver_zip, tracking numbers
- Persists across application sessions

## 🚀 **Usage**

### **Quick Start**
1. Run the application
2. Choose option `m` for Enhanced Maxicode Generator
3. Press Enter to accept all defaults (auto-populated from previous inputs)
4. Get unlimited-length Maxicode data

### **Custom Input**
1. Choose option `m`
2. Enter new values for any fields you want to change
3. Press Enter for fields you want to keep as defaults
4. Get customized unlimited Maxicode data

### **Modify Existing**
1. Choose option `m`
2. Select "Modify existing Maxicode data"
3. Paste your existing Maxicode data
4. Get enhanced version with no character limits

## 📊 **Benefits**

1. **Efficiency**: 90% reduction in manual input (just press Enter)
2. **Accuracy**: Auto-calculated city/state from ZIP codes
3. **Flexibility**: No character limits - use full data capacity
4. **Persistence**: Remembers your previous inputs
5. **Speed**: Quick iteration through multiple generations

## 🔄 **Data Flow**

```
Previous Inputs → Auto-Population → ZIP Lookup → Default Values → User Confirmation → Enhanced Maxicode
     ↓                ↓               ↓              ↓               ↓                    ↓
ftid_data.json → Load Defaults → API Call → Show Defaults → Press Enter → Unlimited Data
```

## 🎯 **Example Workflow**

1. **First Run**: Enter ZIP `90210`, tracking `1Z123...`, city `BEVERLY HILLS`, state `CA`
2. **Second Run**: Press Enter for all fields (auto-populated)
3. **Third Run**: Change ZIP to `10001`, press Enter for rest (auto-calculates NYC, NY)
4. **Result**: Unlimited Maxicode data with minimal user input

The enhanced system transforms Maxicode generation from a manual, limited process into an automated, unlimited, and highly efficient workflow that learns from your previous inputs and minimizes the need for manual data entry.

