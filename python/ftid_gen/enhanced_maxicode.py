import random
import string
import re
import requests
from ftid_gen.data_storage import storage
from ftid_gen.settings_manager import settings
from ftid_gen.address_utils import auto_fill_from_zip

class EnhancedMaxicodeGenerator:
    """Enhanced Maxicode generator with auto-population and no character limits"""
    
    def __init__(self):
        self.previous_data = self._load_previous_data()
    
    def _load_previous_data(self):
        """Load previous user input data"""
        return {
            'zip_code': storage.get_previous('receiver_zip') or '',
            'tracking_number': storage.get_previous('ups_tracking') or storage.get_previous('usps_tracking') or storage.get_previous('fedex_tracking') or '',
            'city': '',
            'state': '',
            'country_code': '840',
            'service_class': '001',
            'scac': 'UPSN',
            'shipper_number': '',
            'package_weight': ''
        }
    
    def _get_city_state_from_zip(self, zip_code):
        """Get city and state from zip code"""
        if not zip_code or len(zip_code) != 5:
            return None, None
        
        location_info = auto_fill_from_zip(zip_code)
        if location_info:
            return location_info['city'].upper(), location_info['state'].upper()
        return None, None
    
    def _get_user_input_with_default(self, prompt, default_value, validation_func=None):
        """Get user input with default value that can be accepted with Enter"""
        if default_value:
            user_input = input(f"{prompt} (default: {default_value}): ").strip()
            if not user_input:
                return default_value
            if validation_func and not validation_func(user_input):
                print(f"⚠️ Invalid input, using default: {default_value}")
                return default_value
            return user_input
        else:
            return input(f"{prompt}: ").strip()
    
    def _validate_zip(self, zip_code):
        """Validate ZIP code format"""
        return len(zip_code) == 5 and zip_code.isdigit()
    
    def _validate_tracking(self, tracking):
        """Validate tracking number format"""
        return len(tracking) > 0
    
    def _validate_state(self, state):
        """Validate state format"""
        return len(state) == 2 and state.isalpha()
    
    def create_maxicode_from_scratch(self):
        """Create MaxiCode data from scratch with auto-populated defaults"""
        print("\n=== ENHANCED MAXICODE GENERATOR ===")
        print("Using your previous inputs automatically...")
        
        # Auto-use ZIP code from previous data
        zip_code = self.previous_data['zip_code']
        if not zip_code or not self._validate_zip(zip_code):
            print("⚠️ No valid previous ZIP code found, generating random")
            zip_code = ''.join(random.choices(string.digits, k=5))
        
        print(f"📍 Using ZIP: {zip_code}")
        
        # Auto-calculate city and state from ZIP
        city, state = self._get_city_state_from_zip(zip_code)
        if city and state:
            print(f"📍 Auto-detected: {city}, {state}")
            self.previous_data['city'] = city
            self.previous_data['state'] = state
        else:
            # Use previous city/state if available
            city = self.previous_data['city'] or "NEW YORK"
            state = self.previous_data['state'] or "NY"
            print(f"📍 Using previous: {city}, {state}")
        
        # Auto-use tracking number from previous data
        tracking_number = self.previous_data['tracking_number']
        if not tracking_number:
            tracking_number = "1Z" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
            print(f"⚠️ Generated random tracking number: {tracking_number}")
        else:
            print(f"🚚 Using tracking: {tracking_number}")
        
        # Auto-set other fields
        country_code = self.previous_data['country_code'] or "840"
        service_class = self.previous_data['service_class'] or "001"
        scac = self.previous_data['scac'] or "UPSN"
        
        # Generate shipper number if not provided
        shipper_number = self.previous_data['shipper_number']
        if not shipper_number:
            shipper_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Generate package weight if not provided
        package_weight = self.previous_data['package_weight']
        if not package_weight:
            package_weight = str(random.randint(1, 999)).zfill(3)
        
        print(f"🏢 Using SCAC: {scac}")
        print(f"📦 Using shipper: {shipper_number}")
        print(f"⚖️ Using weight: {package_weight}")
        
        # Build MaxiCode data string with NO character limit
        maxicode_data = self._build_maxicode_data(
            zip_code, country_code, service_class, tracking_number,
            scac, shipper_number, package_weight, city, state
        )
        
        # Save current values for next time
        self._save_current_data(zip_code, tracking_number, city, state, 
                               country_code, service_class, scac, shipper_number, package_weight)
        
        print(f"\n✅ Created Enhanced MaxiCode data:")
        print(f"📦 ZIP: {zip_code}, Country: {country_code}, Service: {service_class}")
        print(f"🚚 Tracking: {tracking_number}")
        print(f"🏢 SCAC: {scac}, Shipper: {shipper_number}")
        print(f"⚖️ Weight: {package_weight}, City: {city}, State: {state}")
        print(f"📏 Total length: {len(maxicode_data)} characters (NO LIMIT)")
        print(f"🔤 Data: {repr(maxicode_data)}")
        
        return maxicode_data
    
    def _build_maxicode_data(self, zip_code, country_code, service_class, tracking_number,
                           scac, shipper_number, package_weight, city, state):
        """Build MaxiCode data string with no character limit"""
        
        # Use ASCII control characters
        rs_char = chr(30)  # Record Separator (\x1e)
        gs_char = chr(29)  # Group Separator (\x1d)
        eot_char = chr(4)  # End of Transmission (\x04)
        
        # Generate additional fields to fill space (no limit)
        random_field1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
        random_field2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        random_field3 = '1/1'  # Package sequence
        random_field4 = ''.join(random.choices(string.digits, k=3))
        
        # Add more random fields for extended data
        extended_field1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        extended_field2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        extended_field3 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        
        # Construct the MaxiCode data with NO character limit
        maxicode_data = (
            f"[)>{rs_char}01{gs_char}"  # Header
            f"{zip_code}{gs_char}"      # ZIP code
            f"{country_code}{gs_char}"  # Country code
            f"{service_class}{gs_char}" # Service class
            f"{tracking_number}{gs_char}"  # Tracking number
            f"{scac}{gs_char}"          # SCAC
            f"{shipper_number}{gs_char}" # Shipper number
            f"{package_weight}{gs_char}" # Weight
            f"{random_field1}{gs_char}"  # Random field
            f"{random_field2}{gs_char}"  # Random field
            f"{random_field3}{gs_char}"  # Package sequence
            f"{random_field4}{gs_char}"  # Random field
            f"N{gs_char}"               # Fixed field
            f"{random_field1}{gs_char}"  # Random field
            f"{city}{gs_char}"          # City
            f"{state}{gs_char}"         # State
            f"{extended_field1}{gs_char}" # Extended field 1
            f"{extended_field2}{gs_char}" # Extended field 2
            f"{extended_field3}{gs_char}" # Extended field 3
            f"ENHANCED{gs_char}"        # Enhancement marker
            f"{rs_char}"               # Record separator
            f"{eot_char}"              # End of transmission
        )
        
        return maxicode_data
    
    def _save_current_data(self, zip_code, tracking_number, city, state, 
                          country_code, service_class, scac, shipper_number, package_weight):
        """Save current data for next time"""
        storage.save('receiver_zip', zip_code)
        storage.save('ups_tracking', tracking_number)
        
        # Update internal data
        self.previous_data.update({
            'zip_code': zip_code,
            'tracking_number': tracking_number,
            'city': city,
            'state': state,
            'country_code': country_code,
            'service_class': service_class,
            'scac': scac,
            'shipper_number': shipper_number,
            'package_weight': package_weight
        })
    
    def modify_existing_maxicode(self, data):
        """Modify existing MaxiCode data without character limits"""
        print("\n=== MODIFY EXISTING MAXICODE (NO LIMITS) ===")
        
        # Find the start of the MaxiCode header "[)>"
        header_match = re.search(r"\[\)>", data)
        if not header_match:
            print(f"❌ Could not find '[)>' in the data: {repr(data)}")
            return None
        
        # Find 'UPS' (case-sensitive)
        ups_match = re.search(r"UPS", data)
        if not ups_match:
            print(f"❌ Could not find 'UPS' in the data: {repr(data)}")
            return None
        
        # Extract the base segment
        start_index = header_match.start()
        ups_end = ups_match.end()
        
        # Use ALL data after UPS (no 9 character limit)
        base_segment = data[start_index:ups_end]
        remaining_data = data[ups_end:]
        
        print(f"✅ Base segment: '{base_segment}' (length: {len(base_segment)})")
        print(f"✅ Remaining data: '{remaining_data}' (length: {len(remaining_data)})")
        
        # Add extended data without limits
        extended_data = ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))
        
        # Build new MaxiCode with extended data
        gs_char = chr(29)  # Group Separator
        rs_char = chr(30)  # Record Separator
        eot_char = chr(4)  # End of Transmission
        
        enhanced_data = (
            f"{base_segment}"           # Base segment
            f"{remaining_data}"         # Original remaining data
            f"{gs_char}"                # Group separator
            f"EXT{extended_data}"       # Extended data
            f"{rs_char}"                # Record separator
            f"{eot_char}"               # End of transmission
        )
        
        print(f"✅ Enhanced MaxiCode (NO LIMITS):")
        print(f"📏 Total length: {len(enhanced_data)} characters")
        print(f"🔤 Data: {repr(enhanced_data)}")
        
        return enhanced_data

# Global enhanced Maxicode generator instance
enhanced_maxicode = EnhancedMaxicodeGenerator()
