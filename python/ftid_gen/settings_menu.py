import os
import sys
from typing import Optional
from ftid_gen.settings_manager import settings
from ftid_gen.address_utils import lookup_zipcode_info

class SettingsMenu:
    """Interactive settings menu for configuring the application"""
    
    def __init__(self):
        self.current_section = None
    
    def show_main_menu(self):
        """Display the main settings menu"""
        while True:
            print("\n" + "="*60)
            print("⚙️  SETTINGS MENU")
            print("="*60)
            print("1. From Address Settings")
            print("2. Maxicode Settings")
            print("3. Input Field Visibility")
            print("4. File Import Preferences")
            print("5. Previous Maxicode Settings")
            print("6. Zip Code Lookup Settings")
            print("7. UI Preferences")
            print("8. Export Settings")
            print("9. Import Settings")
            print("10. Reset to Defaults")
            print("0. Back to Main Menu")
            
            choice = input("\nEnter your choice: ").strip()

            if not choice:
                choice = "0"
            
            if choice == "0":
                break
            elif choice == "1":
                self._from_address_settings()
            elif choice == "2":
                self._maxicode_settings()
            elif choice == "3":
                self._input_field_settings()
            elif choice == "4":
                self._file_import_settings()
            elif choice == "5":
                self._previous_maxicode_settings()
            elif choice == "6":
                self._zip_lookup_settings()
            elif choice == "7":
                self._ui_preferences()
            elif choice == "8":
                self._export_settings()
            elif choice == "9":
                self._import_settings()
            elif choice == "10":
                self._reset_settings()
            else:
                print("❌ Invalid choice. Please try again.")
    
    def _from_address_settings(self):
        """Configure default From address settings"""
        print("\n" + "="*50)
        print("📍 FROM ADDRESS SETTINGS")
        print("="*50)
        
        current = settings.get_from_address()
        print(f"Current From Address:")
        print(f"  ZIP Code: {current.get('zip_code', 'Not set')}")
        print(f"  City: {current.get('city', 'Not set')}")
        print(f"  State: {current.get('state', 'Not set')}")
        
        print("\n1. Set ZIP Code")
        print("2. Auto-fill City/State from ZIP")
        print("3. Clear From Address")
        print("0. Back")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            self._set_from_zip()
        elif choice == "2":
            self._auto_fill_from_zip()
        elif choice == "3":
            settings.set_from_address()
            print("✅ From address cleared.")
        elif choice == "0":
            return
        else:
            print("❌ Invalid choice.")
    
    def _set_from_zip(self):
        """Set the From ZIP code"""
        while True:
            zip_code = input("Enter From ZIP Code (5 digits): ").strip()
            if len(zip_code) == 5 and zip_code.isdigit():
                # Try to get city/state info
                location_info = lookup_zipcode_info(zip_code)
                if location_info:
                    city = location_info['city']
                    state = location_info['state']
                    settings.set_from_address(zip_code, city, state)
                    print(f"✅ From address set: {city}, {state} {zip_code}")
                else:
                    settings.set_from_address(zip_code, "", "")
                    print(f"✅ ZIP code set: {zip_code} (city/state not found)")
                break
            else:
                print("❌ Please enter a valid 5-digit ZIP code.")
    
    def _auto_fill_from_zip(self):
        """Auto-fill city/state from existing ZIP"""
        current = settings.get_from_address()
        zip_code = current.get('zip_code')
        
        if not zip_code:
            print("❌ No ZIP code set. Please set a ZIP code first.")
            return
        
        print(f"Looking up city/state for ZIP: {zip_code}")
        location_info = lookup_zipcode_info(zip_code)
        
        if location_info:
            city = location_info['city']
            state = location_info['state']
            settings.set_from_address(zip_code, city, state)
            print(f"✅ Updated: {city}, {state} {zip_code}")
        else:
            print("❌ Could not find city/state for this ZIP code.")
    
    def _maxicode_settings(self):
        """Configure Maxicode settings"""
        print("\n" + "="*50)
        print("🔢 MAXICODE SETTINGS")
        print("="*50)
        
        current = settings.get_maxicode_settings()
        print(f"Current Settings:")
        print(f"  Auto-generate: {'Yes' if current.get('auto_generate', True) else 'No'}")
        print(f"  No Character Limit: {'Yes' if current.get('no_character_limit', True) else 'No'}")
        print(f"  Manual Mode: {'Yes' if current.get('manual_mode', False) else 'No'}")
        print(f"  Prompt Input Method: {'Yes' if current.get('prompt_input_method', False) else 'No'}")
        
        print("\n1. Toggle Auto-generation")
        print("2. Toggle No Character Limit")
        print("3. Toggle Manual Mode")
        print("4. Toggle Prompt Input Method (for bulk processing)")
        print("0. Back")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            current_auto = current.get('auto_generate', True)
            new_auto = not current_auto
            settings.set_maxicode_auto_generate(new_auto)
            print(f"✅ Auto-generation {'enabled' if new_auto else 'disabled'}")
        elif choice == "2":
            current_no_limit = current.get('no_character_limit', True)
            new_no_limit = not current_no_limit
            settings.set_maxicode_no_limit(new_no_limit)
            print(f"✅ No character limit {'enabled' if new_no_limit else 'disabled'}")
        elif choice == "3":
            current_manual = current.get('manual_mode', False)
            new_manual = not current_manual
            settings.set('maxicode.manual_mode', new_manual)
            print(f"✅ Manual mode {'enabled' if new_manual else 'disabled'}")
        elif choice == "4":
            current_prompt = current.get('prompt_input_method', False)
            new_prompt = not current_prompt
            settings.set('maxicode.prompt_input_method', new_prompt)
            status = 'enabled' if new_prompt else 'disabled'
            print(f"✅ Prompt input method {status}")
            if not new_prompt:
                print("ℹ️  Bulk processing will automatically create MaxiCode from scratch")
            else:
                print("ℹ️  You will be prompted to choose input method for each MaxiCode")
        elif choice == "0":
            return
        else:
            print("❌ Invalid choice.")
    
    
    def _input_field_settings(self):
        """Configure input field visibility"""
        print("\n" + "="*50)
        print("👁️  INPUT FIELD VISIBILITY")
        print("="*50)
        
        fields = {
            'show_sender_name': 'Sender Name',
            'show_sender_address': 'Sender Address',
            'show_receiver_name': 'Receiver Name',
            'show_receiver_address': 'Receiver Address',
            'show_receiver_zip': 'Receiver ZIP Code',
            'show_tracking_number': 'Tracking Number'
        }
        
        current = settings.get_input_field_visibility()
        
        print("Current visibility:")
        for key, label in fields.items():
            visible = current.get(key, True)
            print(f"  {label}: {'Visible' if visible else 'Hidden'}")
        
        print("\n1. Toggle all fields")
        print("2. Toggle individual field")
        print("3. Show all fields")
        print("4. Hide all fields")
        print("0. Back")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            self._toggle_all_fields()
        elif choice == "2":
            self._toggle_individual_field(fields)
        elif choice == "3":
            for key in fields.keys():
                settings.set_input_field_visibility(key, True)
            print("✅ All fields are now visible")
        elif choice == "4":
            for key in fields.keys():
                settings.set_input_field_visibility(key, False)
            print("✅ All fields are now hidden")
        elif choice == "0":
            return
        else:
            print("❌ Invalid choice.")
    
    def _toggle_all_fields(self):
        """Toggle visibility of all fields"""
        current = settings.get_input_field_visibility()
        all_visible = all(current.get(key, True) for key in current.keys())
        new_state = not all_visible
        
        for key in current.keys():
            settings.set_input_field_visibility(key, new_state)
        
        print(f"✅ All fields {'shown' if new_state else 'hidden'}")
    
    def _toggle_individual_field(self, fields):
        """Toggle individual field visibility"""
        print("\nSelect field to toggle:")
        field_list = list(fields.items())
        for i, (key, label) in enumerate(field_list, 1):
            current_visible = settings.get(f'input_fields.{key}', True)
            print(f"{i}. {label} ({'Visible' if current_visible else 'Hidden'})")
        
        try:
            choice = int(input("Enter field number: ").strip())
            if 1 <= choice <= len(field_list):
                key = field_list[choice - 1][0]
                current_visible = settings.get(f'input_fields.{key}', True)
                new_visible = not current_visible
                settings.set_input_field_visibility(key, new_visible)
                print(f"✅ {fields[key]} is now {'visible' if new_visible else 'hidden'}")
            else:
                print("❌ Invalid field number.")
        except ValueError:
            print("❌ Please enter a valid number.")
    
    def _file_import_settings(self):
        """Configure file import preferences"""
        print("\n" + "="*50)
        print("📁 FILE IMPORT PREFERENCES")
        print("="*50)
        
        current = settings.get_file_import_settings()
        print(f"Current Settings:")
        print(f"  Default Format: {current.get('default_format', 'excel')}")
        print(f"  Auto-detect Columns: {'Yes' if current.get('auto_detect_columns', True) else 'No'}")
        print(f"  Batch Processing: {'Yes' if current.get('batch_processing', True) else 'No'}")
        
        print("\n1. Set Default Format")
        print("2. Toggle Auto-detect Columns")
        print("3. Toggle Batch Processing")
        print("0. Back")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            print("1. Excel (.xlsx)")
            print("2. CSV (.csv)")
            format_choice = input("Select format: ").strip()
            if format_choice == "1":
                settings.set('file_import.default_format', 'excel')
                print("✅ Default format set to Excel")
            elif format_choice == "2":
                settings.set('file_import.default_format', 'csv')
                print("✅ Default format set to CSV")
            else:
                print("❌ Invalid choice.")
        elif choice == "2":
            current_auto = current.get('auto_detect_columns', True)
            new_auto = not current_auto
            settings.set('file_import.auto_detect_columns', new_auto)
            print(f"✅ Auto-detect columns {'enabled' if new_auto else 'disabled'}")
        elif choice == "3":
            current_batch = current.get('batch_processing', True)
            new_batch = not current_batch
            settings.set('file_import.batch_processing', new_batch)
            print(f"✅ Batch processing {'enabled' if new_batch else 'disabled'}")
        elif choice == "0":
            return
        else:
            print("❌ Invalid choice.")
    
    def _previous_maxicode_settings(self):
        """Configure previous Maxicode settings"""
        print("\n" + "="*50)
        print("📋 PREVIOUS MAXICODE SETTINGS")
        print("="*50)
        
        current = settings.get_previous_maxicode_settings()
        print(f"Current Settings:")
        print(f"  Enabled: {'Yes' if current.get('enabled', True) else 'No'}")
        print(f"  Max Entries: {current.get('max_entries', 3)}")
        print(f"  Show Preview: {'Yes' if current.get('show_preview', True) else 'No'}")
        
        print("\n1. Toggle Enabled")
        print("2. Set Max Entries")
        print("3. Toggle Preview")
        print("0. Back")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            current_enabled = current.get('enabled', True)
            new_enabled = not current_enabled
            settings.set('previous_maxicode.enabled', new_enabled)
            print(f"✅ Previous Maxicode {'enabled' if new_enabled else 'disabled'}")
        elif choice == "2":
            try:
                entries = int(input("Enter max entries (1-10): ").strip())
                if 1 <= entries <= 10:
                    settings.set('previous_maxicode.max_entries', entries)
                    print(f"✅ Max entries set to {entries}")
                else:
                    print("❌ Please enter a number between 1 and 10.")
            except ValueError:
                print("❌ Please enter a valid number.")
        elif choice == "3":
            current_preview = current.get('show_preview', True)
            new_preview = not current_preview
            settings.set('previous_maxicode.show_preview', new_preview)
            print(f"✅ Preview {'enabled' if new_preview else 'disabled'}")
        elif choice == "0":
            return
        else:
            print("❌ Invalid choice.")
    
    def _zip_lookup_settings(self):
        """Configure zip code lookup settings"""
        print("\n" + "="*50)
        print("🔍 ZIP CODE LOOKUP SETTINGS")
        print("="*50)
        
        current = settings.get_zip_lookup_settings()
        print(f"Current Settings:")
        print(f"  Auto-identify: {'Yes' if current.get('auto_identify', True) else 'No'}")
        print(f"  Use API Fallback: {'Yes' if current.get('use_api_fallback', True) else 'No'}")
        print(f"  Cache Results: {'Yes' if current.get('cache_results', True) else 'No'}")
        
        print("\n1. Toggle Auto-identify")
        print("2. Toggle API Fallback")
        print("3. Toggle Cache Results")
        print("0. Back")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            current_auto = current.get('auto_identify', True)
            new_auto = not current_auto
            settings.set('zip_lookup.auto_identify', new_auto)
            print(f"✅ Auto-identify {'enabled' if new_auto else 'disabled'}")
        elif choice == "2":
            current_api = current.get('use_api_fallback', True)
            new_api = not current_api
            settings.set('zip_lookup.use_api_fallback', new_api)
            print(f"✅ API fallback {'enabled' if new_api else 'disabled'}")
        elif choice == "3":
            current_cache = current.get('cache_results', True)
            new_cache = not current_cache
            settings.set('zip_lookup.cache_results', new_cache)
            print(f"✅ Cache results {'enabled' if new_cache else 'disabled'}")
        elif choice == "0":
            return
        else:
            print("❌ Invalid choice.")
    
    def _ui_preferences(self):
        """Configure UI preferences"""
        print("\n" + "="*50)
        print("🎨 UI PREFERENCES")
        print("="*50)
        
        current = settings.get('ui', {})
        print(f"Current Settings:")
        print(f"  Show Tooltips: {'Yes' if current.get('show_tooltips', True) else 'No'}")
        print(f"  Compact Mode: {'Yes' if current.get('compact_mode', False) else 'No'}")
        print(f"  Theme: {current.get('theme', 'default')}")
        
        print("\n1. Toggle Tooltips")
        print("2. Toggle Compact Mode")
        print("3. Change Theme")
        print("0. Back")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            current_tooltips = current.get('show_tooltips', True)
            new_tooltips = not current_tooltips
            settings.set('ui.show_tooltips', new_tooltips)
            print(f"✅ Tooltips {'enabled' if new_tooltips else 'disabled'}")
        elif choice == "2":
            current_compact = current.get('compact_mode', False)
            new_compact = not current_compact
            settings.set('ui.compact_mode', new_compact)
            print(f"✅ Compact mode {'enabled' if new_compact else 'disabled'}")
        elif choice == "3":
            print("1. Default")
            print("2. Dark")
            print("3. Light")
            theme_choice = input("Select theme: ").strip()
            themes = {"1": "default", "2": "dark", "3": "light"}
            if theme_choice in themes:
                settings.set('ui.theme', themes[theme_choice])
                print(f"✅ Theme set to {themes[theme_choice]}")
            else:
                print("❌ Invalid choice.")
        elif choice == "0":
            return
        else:
            print("❌ Invalid choice.")
    
    def _export_settings(self):
        """Export settings to a file"""
        file_path = input("Enter file path for export (or press Enter for default): ").strip()
        if not file_path:
            file_path = "ftid_settings_export.json"
        
        if settings.export_settings(file_path):
            print(f"✅ Settings exported to {file_path}")
        else:
            print("❌ Failed to export settings.")
    
    def _import_settings(self):
        """Import settings from a file"""
        file_path = input("Enter file path to import from: ").strip()
        
        if not os.path.exists(file_path):
            print("❌ File not found.")
            return
        
        confirm = input("This will overwrite current settings. Continue? (y/N): ").strip().lower()
        if confirm == 'y':
            if settings.import_settings(file_path):
                print("✅ Settings imported successfully.")
            else:
                print("❌ Failed to import settings.")
        else:
            print("❌ Import cancelled.")
    
    def _reset_settings(self):
        """Reset all settings to defaults"""
        confirm = input("This will reset ALL settings to defaults. Continue? (y/N): ").strip().lower()
        if confirm == 'y':
            settings.reset_to_defaults()
            print("✅ Settings reset to defaults.")
        else:
            print("❌ Reset cancelled.")

# Global settings menu instance
settings_menu = SettingsMenu()


