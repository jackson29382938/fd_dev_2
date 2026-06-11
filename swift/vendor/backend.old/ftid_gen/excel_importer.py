import os
import pandas as pd
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from ftid_gen.settings_manager import settings
from ftid_gen.address_utils import auto_fill_from_zip, generate_fake_address
from ftid_gen.data_storage import storage
from ftid_gen.tracking_utils import (
    get_valid_ups_tracking, 
    get_valid_usps_tracking, 
    get_valid_fedex_tracking,
    modify_tracking_number,
    modify_usps_tracking_number,
    modify_fedex_tracking_number
)


def _clean_import_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _normalize_import_zip(value) -> str:
    text = _clean_import_text(value).replace(" ", "")
    if not text:
        return ""
    if "-" in text:
        first, *rest = text.split("-")
        if first.isdigit() and len(first) < 5:
            first = first.zfill(5)
        return "-".join([first, *rest])
    if text.isdigit() and len(text) < 5:
        return text.zfill(5)
    return text


class ExcelImporter:
    """Handles Excel file import and batch processing"""
    
    def __init__(self):
        self.supported_formats = ['.xlsx', '.xls', '.csv']
        self.last_created_file = None  # Track the last created template file
        self.last_skipped_rows = []  # Rows skipped during the most recent batch
        self.column_mappings = {
            'tracking_number': ['tracking', 'tracking_number', 'track', 'tracking_id'],
            'sender_zip': ['sender_zip', 'from_zip', 'origin_zip', 'sender_zipcode'],
            'receiver_zip': ['receiver_zip', 'to_zip', 'destination_zip', 'receiver_zipcode'],
            'sender_name': ['sender_name', 'from_name', 'origin_name', 'sender'],
            'receiver_name': ['receiver_name', 'to_name', 'destination_name', 'receiver'],
            'sender_address': ['sender_address', 'from_address', 'origin_address'],
            'receiver_address': ['receiver_address', 'to_address', 'destination_address'],
            'method': ['method', 'carrier', 'shipping_method', 'service']
        }
    
    def import_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """Import data from Excel or CSV file"""
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext not in self.supported_formats:
            print(f"❌ Unsupported file format: {file_ext}")
            print(f"Supported formats: {', '.join(self.supported_formats)}")
            return None
        
        try:
            if file_ext == '.csv':
                df = pd.read_csv(file_path, dtype=str, keep_default_na=False, na_filter=False)
            else:
                df = pd.read_excel(file_path, dtype=str, keep_default_na=False, na_filter=False)
            
            print(f"✅ Successfully imported {len(df)} rows from {file_path}")
            return df
            
        except Exception as e:
            print(f"❌ Error importing file: {e}")
            return None
    
    def auto_detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """Auto-detect column mappings based on column names"""
        mappings = {}
        df_columns = [col.lower().strip() for col in df.columns]
        
        for field, possible_names in self.column_mappings.items():
            # Sort possible names by length (longest first) to prefer more specific matches
            sorted_names = sorted(possible_names, key=len, reverse=True)
            
            for col_name in df_columns:
                # First try exact match
                if col_name in sorted_names:
                    original_col = next((col for col in df.columns if col.lower().strip() == col_name), None)
                    if original_col:
                        mappings[field] = original_col
                        break
                
                # Then try substring match with longer/more specific patterns first
                for name in sorted_names:
                    if name in col_name:
                        # Find the original column name (case-sensitive)
                        original_col = next((col for col in df.columns if col.lower().strip() == col_name), None)
                        if original_col:
                            mappings[field] = original_col
                            break
                
                if field in mappings:
                    break
        
        return mappings
    
    def show_column_mapping_menu(self, df: pd.DataFrame, auto_mappings: Dict[str, str]) -> Dict[str, str]:
        """Show interactive menu for column mapping"""
        print("\n" + "="*60)
        print("📊 COLUMN MAPPING")
        print("="*60)
        
        print("Available columns:")
        for i, col in enumerate(df.columns, 1):
            print(f"{i}. {col}")
        
        print("\nAuto-detected mappings:")
        for field, col in auto_mappings.items():
            print(f"  {field}: {col}")
        
        print("\nRequired fields:")
        required_fields = ['tracking_number', 'sender_zip', 'receiver_zip']
        optional_fields = ['sender_name', 'receiver_name', 'sender_address', 'receiver_address', 'method']
        
        for field in required_fields:
            print(f"  {field} (required)")
        for field in optional_fields:
            print(f"  {field} (optional)")
        
        mappings = auto_mappings.copy()
        
        print("\n1. Use auto-detected mappings")
        print("2. Manually map columns")
        print("0. Cancel")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            return mappings
        elif choice == "2":
            return self._manual_column_mapping(df, mappings)
        elif choice == "0":
            return {}
        else:
            print("❌ Invalid choice.")
            return {}
    
    def _manual_column_mapping(self, df: pd.DataFrame, current_mappings: Dict[str, str]) -> Dict[str, str]:
        """Manual column mapping interface"""
        mappings = current_mappings.copy()
        
        fields = ['tracking_number', 'sender_zip', 'receiver_zip', 'sender_name', 
                 'receiver_name', 'sender_address', 'receiver_address', 'method']
        
        for field in fields:
            if field in mappings:
                print(f"\n{field}: {mappings[field]} (current)")
            else:
                print(f"\n{field}: Not mapped")
            
            print("Available columns:")
            for i, col in enumerate(df.columns, 1):
                print(f"{i}. {col}")
            
            while True:
                choice = input(f"Select column for {field} (or press Enter to skip): ").strip()
                if not choice:
                    break
                
                try:
                    col_index = int(choice) - 1
                    if 0 <= col_index < len(df.columns):
                        mappings[field] = df.columns[col_index]
                        break
                    else:
                        print("❌ Invalid column number.")
                except ValueError:
                    print("❌ Please enter a valid number.")
        
        return mappings
    
    def process_batch(self, df: pd.DataFrame, mappings: Dict[str, str]) -> List[Dict[str, Any]]:
        """Process all rows in the DataFrame"""
        if not settings.get('file_import.batch_processing', True):
            print("❌ Batch processing is disabled in settings.")
            return []
        
        results = []
        self.last_skipped_rows = []
        required_fields = ['tracking_number', 'sender_zip', 'receiver_zip']
        
        # Check if all required fields are mapped
        missing_fields = [field for field in required_fields if field not in mappings]
        if missing_fields:
            print(f"❌ Missing required field mappings: {', '.join(missing_fields)}")
            return []
        
        print(f"\n🔄 Processing {len(df)} rows...")
        
        for index, row in df.iterrows():
            row_num = index + 1
            try:
                result = self._process_single_row(row, mappings, row_num)
                if result:
                    results.append(result)
            except Exception as e:
                reason = str(e) or "Unknown error"
                print(f"❌ Error processing row {row_num}: {reason}")
                self.last_skipped_rows.append({"row_number": row_num, "reason": reason})
                continue
        
        print(f"✅ Successfully processed {len(results)} out of {len(df)} rows")
        return results
    
    def _process_single_row(self, row: pd.Series, mappings: Dict[str, str], row_num: int) -> Optional[Dict[str, Any]]:
        """Process a single row of data"""
        # Extract basic information
        tracking_number = _clean_import_text(row[mappings['tracking_number']])
        sender_zip = _normalize_import_zip(row[mappings['sender_zip']])
        receiver_zip = _normalize_import_zip(row[mappings['receiver_zip']])
        
        missing = [
            label
            for label, value in (
                ("tracking number", tracking_number),
                ("sender ZIP", sender_zip),
                ("receiver ZIP", receiver_zip),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required {', '.join(missing)}")
        
        # Determine method if not provided
        method = mappings.get('method')
        if method and method in row:
            method = _clean_import_text(row[method]).upper()
        else:
            # Auto-detect method from tracking number
            method = self._detect_method_from_tracking(tracking_number)
        
        # Generate addresses
        sender_info = self._generate_address_info(sender_zip, row, mappings, 'sender')
        receiver_info = self._generate_address_info(receiver_zip, row, mappings, 'receiver')
        
        if not sender_info:
            raise ValueError(f"Could not resolve a sender address for ZIP {sender_zip}")
        if not receiver_info:
            raise ValueError(f"Could not resolve a receiver address for ZIP {receiver_zip}")
        
        # Generate modified tracking number
        modified_tracking = self._generate_modified_tracking(tracking_number, method)
        
        return {
            'row_number': row_num,
            'original_tracking': tracking_number,
            'modified_tracking': modified_tracking,
            'method': method,
            'sender_info': sender_info,
            'receiver_info': receiver_info,
            'sender_zip': sender_zip,
            'receiver_zip': receiver_zip
        }
    
    def _detect_method_from_tracking(self, tracking_number: str) -> str:
        """Detect shipping method from tracking number format"""
        tracking_number = tracking_number.strip().replace(' ', '').upper()
        
        if tracking_number.startswith('1Z') and len(tracking_number) == 18:
            return 'FTID_UPS'
        elif len(tracking_number) == 22 and tracking_number.isdigit():
            return 'FTID_USPS'
        elif len(tracking_number) >= 12 and tracking_number.isdigit():
            return 'FTID_FEDEX'
        else:
            return 'FTID_UPS'  # Default fallback
    
    def _generate_address_info(self, zip_code: str, row: pd.Series, mappings: Dict[str, str], prefix: str) -> Optional[Dict[str, str]]:
        """Generate address information for sender or receiver"""
        zip_code = _normalize_import_zip(zip_code)
        # Try to get name from mapping
        name_field = f'{prefix}_name'
        name = None
        if name_field in mappings and mappings[name_field] in row:
            name = str(row[mappings[name_field]]).strip()
            # Check if name is valid (not empty, not NaN, not a zip code)
            if name.lower() == 'nan' or not name or name.isdigit():
                name = None
        
        if not name:
            from ftid_gen.address_utils import generate_full_name
            name = generate_full_name()
        
        # Try to get address from mapping
        address_field = f'{prefix}_address'
        address = None
        if address_field in mappings and mappings[address_field] in row:
            address = str(row[mappings[address_field]]).strip()
            # Check if address is valid (not empty, not NaN, not a zip code)
            if address.lower() == 'nan' or not address or address.isdigit():
                address = None
        
        if not address:
            # Try to get real address from Yelp first
            from ftid_gen.address_utils import search_yelp_for_address
            address_info = search_yelp_for_address(zip_code)
            
            # Fall back to fake address if Yelp fails
            if not address_info:
                print(f"  ⚠️ No Yelp addresses found for {zip_code}, using generated address")
                address_info = generate_fake_address(zip_code)
            
            if address_info:
                address = address_info['address']
                city = address_info['city']
                state = address_info['state']
            else:
                return None
        else:
            # Auto-fill city/state from zip
            location_info = auto_fill_from_zip(zip_code)
            if location_info:
                city = location_info['city']
                state = location_info['state']
            else:
                city = "Unknown City"
                state = "XX"
        
        return {
            'name': name,
            'address': address,
            'city': city,
            'state': state,
            'zip_code': zip_code
        }
    
    def _generate_modified_tracking(self, tracking_number: str, method: str) -> str:
        """Generate modified tracking number based on method"""
        try:
            if method == 'FTID_UPS':
                return modify_tracking_number(tracking_number)
            elif method == 'FTID_USPS':
                return modify_usps_tracking_number(tracking_number)
            elif method == 'FTID_FEDEX':
                return modify_fedex_tracking_number(tracking_number)
            else:
                return modify_tracking_number(tracking_number)  # Default to UPS
        except Exception as e:
            print(f"Warning: Could not modify tracking number {tracking_number}: {e}")
            return tracking_number
    
    def create_template_file(self) -> Optional[str]:
        """Create a template Excel file with proper columns"""
        try:
            # Create timestamp for unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ftid_import_template_{timestamp}.xlsx"
            
            # Create template DataFrame with example data
            template_data = {
                'tracking_number': ['1Z9999999999999999', '420123456789012345678901', '123456789012'],
                'sender_zip': ['10001', '90210', '60601'],
                'receiver_zip': ['90210', '10001', '33101'],
                'sender_name': ['', '', ''],  # Optional: leave empty to auto-generate
                'receiver_name': ['', '', ''],  # Optional: leave empty to auto-generate
                'sender_address': ['', '', ''],  # Optional: leave empty to auto-generate
                'receiver_address': ['', '', ''],  # Optional: leave empty to auto-generate
                'method': ['FTID_UPS', 'FTID_USPS', 'FTID_FEDEX']  # Optional: auto-detect from tracking
            }
            
            df = pd.DataFrame(template_data)
            
            # Save to Excel with instructions
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Data', index=False)
                
                # Create instructions sheet
                instructions = pd.DataFrame({
                    'INSTRUCTIONS': [
                        'REQUIRED COLUMNS:',
                        '• tracking_number - The tracking number for the shipment',
                        '• sender_zip - ZIP code of the sender',
                        '• receiver_zip - ZIP code of the receiver',
                        '',
                        'OPTIONAL COLUMNS:',
                        '• sender_name - Leave empty to auto-generate random names',
                        '• receiver_name - Leave empty to auto-generate random names',
                        '• sender_address - Leave empty to auto-generate random addresses',
                        '• receiver_address - Leave empty to auto-generate random addresses',
                        '• method - Auto-detected from tracking format (FTID_UPS, FTID_USPS, FTID_FEDEX)',
                        '',
                        'TRACKING NUMBER FORMATS:',
                        '• UPS: 18 characters starting with 1Z (e.g., 1Z9999999999999999)',
                        '• USPS: 22 digits (e.g., 420123456789012345678901)',
                        '• FedEx: 12+ digits (e.g., 123456789012)',
                        '',
                        'Delete the example rows on the Data sheet and add your own data.',
                        'Save the file when done, then return to the program.'
                    ]
                })
                instructions.to_excel(writer, sheet_name='Instructions', index=False)
            
            print(f"\n✅ Template file created: {filename}")
            self.last_created_file = filename
            return filename
            
        except Exception as e:
            print(f"❌ Error creating template file: {e}")
            return None
    
    def open_file_in_excel(self, file_path: str) -> bool:
        """Open the Excel file in the default application"""
        try:
            # For macOS, use 'open' command
            subprocess.run(['open', file_path], check=True)
            print(f"\n📂 Opening {file_path} in Excel...")
            return True
        except Exception as e:
            print(f"❌ Error opening file: {e}")
            print(f"Please manually open: {file_path}")
            return False
    
    def _save_file_to_history(self, file_path: str):
        """Save file path to history for reuse"""
        try:
            # Get absolute path
            abs_path = os.path.abspath(file_path)
            
            # Get existing history
            history = storage.get_previous('excel_file_history') or []
            
            # Add to history if not already there
            if abs_path not in history:
                history.insert(0, abs_path)  # Add to front
                # Keep only last 10 files
                history = history[:10]
                storage.save('excel_file_history', history)
        except Exception as e:
            print(f"Warning: Could not save file to history: {e}")
    
    def _show_previous_files_menu(self) -> Optional[str]:
        """Show menu of previous Excel files and return selected file path"""
        history = storage.get_previous('excel_file_history') or []
        
        if not history:
            print("\n❌ No previous Excel files found.")
            return None
        
        # Filter out files that no longer exist
        valid_files = [f for f in history if os.path.exists(f)]
        
        if not valid_files:
            print("\n❌ No previous Excel files are still available.")
            # Clear invalid history
            storage.save('excel_file_history', [])
            return None
        
        # Update history to only valid files
        if len(valid_files) != len(history):
            storage.save('excel_file_history', valid_files)
        
        print("\n" + "="*60)
        print("📋 PREVIOUS EXCEL FILES")
        print("="*60)
        
        for idx, file_path in enumerate(valid_files, 1):
            # Show filename and directory
            filename = os.path.basename(file_path)
            directory = os.path.dirname(file_path)
            print(f"{idx}. {filename}")
            print(f"   Path: {directory}")
        
        print("0. Cancel")
        
        while True:
            choice = input("\nSelect a file number: ").strip()
            
            if choice == "0":
                return None
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(valid_files):
                    return valid_files[idx]
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a valid number.")
    
    def show_import_menu(self) -> Optional[List[Dict[str, Any]]]:
        """Show the main import menu with options to create new or use existing file"""
        print("\n" + "="*60)
        print("📁 EXCEL/CSV IMPORT")
        print("="*60)
        print("\nChoose import method:")
        print("1. Create new template Excel file (auto-opens for editing)")
        print("2. Use existing Excel/CSV file")
        print("3. Reuse previous Excel/CSV file")
        print("0. Cancel")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            # Option 1: Create new template
            print("\n📝 Creating new template Excel file...")
            file_path = self.create_template_file()
            
            if not file_path:
                return None
            
            # Open the file for editing
            self.open_file_in_excel(file_path)
            
            print("\n" + "="*60)
            print("📋 INSTRUCTIONS:")
            print("1. The template file has been opened in Excel")
            print("2. Delete the example rows and add your data")
            print("3. Required columns: tracking_number, sender_zip, receiver_zip")
            print("4. Leave name/address columns EMPTY to auto-generate")
            print("5. Save the file and close Excel")
            print("6. Press Enter here when ready to continue")
            print("="*60)
            
            input("\nPress Enter when you've finished editing the file...")
            
            # Verify file still exists
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                return None
            
            print(f"\n🔄 Processing file: {file_path}")
            
        elif choice == "2":
            # Option 2: Use existing file
            print("\n" + "="*60)
            print("Expected file format:")
            print("- Required columns: tracking_number, sender_zip, receiver_zip")
            print("- Optional columns: sender_name, receiver_name, sender_address, receiver_address, method")
            print("- Header row required; CSV or Excel (.csv, .xlsx, .xls)")
            print("- Column names can be flexible (we auto-detect common variants)")
            
            file_path = input("\nEnter path to Excel/CSV file: ").strip()
            
            if not file_path:
                print("❌ No file path provided.")
                return None
        
        elif choice == "3":
            # Option 3: Reuse previous file
            file_path = self._show_previous_files_menu()
            
            if not file_path:
                return None
            
            print(f"\n🔄 Selected: {os.path.basename(file_path)}")
        
        elif choice == "0":
            print("❌ Import cancelled.")
            return None
        
        else:
            print("❌ Invalid choice.")
            return None
        
        # Save file to history for future reuse
        self._save_file_to_history(file_path)
        
        # Import the file (common path for all options)
        df = self.import_file(file_path)
        if df is None:
            return None
        
        # Show file info
        print(f"\nFile Info:")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {len(df.columns)}")
        print(f"  Column names: {', '.join(df.columns)}")
        
        # Auto-detect columns
        auto_mappings = self.auto_detect_columns(df)
        
        # Show mapping menu
        mappings = self.show_column_mapping_menu(df, auto_mappings)
        if not mappings:
            return None
        
        # Process the batch
        results = self.process_batch(df, mappings)
        
        if results:
            print(f"\n✅ Import completed successfully!")
            print(f"Processed {len(results)} rows")
            
            # Show summary
            methods = {}
            for result in results:
                method = result['method']
                methods[method] = methods.get(method, 0) + 1
            
            print("\nSummary by method:")
            for method, count in methods.items():
                print(f"  {method}: {count} labels")
        
        return results

# Global Excel importer instance
excel_importer = ExcelImporter()



