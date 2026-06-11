import os
import json
import random
import requests
from pydash import get as _
from ftid_gen.config import API_KEY, FIRST_NAMES, LAST_NAMES, ZIPCODE_FILE
from ftid_gen.tracking_utils import BackStep
from ftid_gen.data_storage import storage

# Module-level cache for ZIP codes (loaded once, reused throughout)
_zipcode_cache = None

def _get_zipcode_cache():
    """Load ZIP codes once and cache them"""
    global _zipcode_cache
    if _zipcode_cache is None and os.path.exists(ZIPCODE_FILE):
        try:
            with open(ZIPCODE_FILE, "r", encoding="utf-8") as f:
                _zipcode_cache = json.load(f)
        except Exception:
            _zipcode_cache = {}
    return _zipcode_cache or {}

def generate_full_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def lookup_zipcode_info(zipcode):
    """
    Look up city and state information for a given zip code using Zippopotamus API
    Returns a dict with 'city' and 'state' keys, or None if lookup fails
    """
    try:
        url = f"https://api.zippopotam.us/us/{zipcode}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            places = data.get('places', [])
            if places:
                place = places[0]  # Use the first place if multiple exist
                return {
                    'city': place.get('place name', 'Unknown City'),
                    'state': place.get('state abbreviation', 'XX')
                }
    except Exception as e:
        print(f"Warning: Could not lookup zip code {zipcode}: {e}")
    
    return None

def get_zipcode_info_from_file_or_api(zipcode):
    """
    Try to get city/state info from cached local JSON file first, then fall back to API
    """
    # First try the cached local file
    zipcodes = _get_zipcode_cache()
    if zipcodes:
        zipcode_info = zipcodes.get(zipcode, {})
        city = zipcode_info.get("city")
        state = zipcode_info.get("state")
        
        if city and state:
            return {'city': city, 'state': state}
    
    # Fall back to API lookup
    print(f"Looking up zip code {zipcode} online...")
    return lookup_zipcode_info(zipcode)

def get_valid_zipcode(prompt='Enter Zip Code: ', storage_key=None):
    # Check for previous data
    previous_zip = None
    if storage_key:
        previous_zip = storage.get_previous(storage_key)
    
    if not os.path.exists(ZIPCODE_FILE):
        print("Warning: zipcodes.json not found. Will validate zip codes online.")
        
        while True:
            if previous_zip:
                print(f"Previous {storage_key}: {previous_zip}")
                zipcode = input(f"{prompt}(Enter=use previous, 'b'=back): ").strip()
            else:
                zipcode = input(f"{prompt}('b'=back): ").strip()
            
            if zipcode.lower() == 'b':
                raise BackStep()
            elif zipcode == '' and previous_zip:
                if storage_key:
                    storage.save(storage_key, previous_zip)
                return previous_zip
            elif len(zipcode) == 5 and zipcode.isdigit():
                # Quick validation - try to lookup the zip code
                info = lookup_zipcode_info(zipcode)
                if info:
                    if storage_key:
                        storage.save(storage_key, zipcode)
                    return zipcode
                else:
                    print("Please enter a valid US zip code.")
            else:
                print("Please enter a 5-digit zip code.")
    else:
        # Original file-based validation
        with open(ZIPCODE_FILE, "r", encoding="utf-8") as f:
            zipcodes = json.load(f)
            
        while True:
            if previous_zip:
                print(f"Previous {storage_key}: {previous_zip}")
                zipcode = input(f"{prompt}(Enter=use previous, 'b'=back): ").strip()
            else:
                zipcode = input(f"{prompt}('b'=back): ").strip()
            
            if zipcode.lower() == 'b':
                raise BackStep()
            elif zipcode == '' and previous_zip:
                if storage_key:
                    storage.save(storage_key, previous_zip)
                return previous_zip
            elif zipcode in zipcodes:
                if storage_key:
                    storage.save(storage_key, zipcode)
                return zipcode
            print("Please enter a valid zip code.")

def generate_fake_address(zipcode):
    """Generate a fake address within the given zip code"""
    # Common street names
    street_names = [
        "Main", "First", "Second", "Third", "Park", "Washington", "Lincoln", 
        "Jefferson", "Madison", "Jackson", "Franklin", "Roosevelt", "Wilson",
        "Oak", "Pine", "Maple", "Cedar", "Elm", "Walnut", "Cherry", "Birch",
        "Spring", "Summer", "Winter", "Autumn", "Hill", "Valley", "Ridge",
        "Lake", "River", "Creek", "Mill", "Church", "School", "Market"
    ]
    
    # Street types
    street_types = ["St", "Ave", "Rd", "Dr", "Ln", "Blvd", "Ct", "Pl", "Way", "Cir"]
    
    # Generate street number (100-9999)
    street_number = random.randint(100, 9999)
    
    # Generate street name and type
    street_name = random.choice(street_names)
    street_type = random.choice(street_types)
    
    # Create full address
    address = f"{street_number} {street_name} {street_type}"
    
    # Get city and state from file or API
    location_info = get_zipcode_info_from_file_or_api(zipcode)
    
    if location_info:
        city = location_info['city']
        state = location_info['state']
    else:
        print(f"Warning: Could not determine city/state for zip code {zipcode}")
        city = "Unknown City"
        state = "XX"
    
    return {
        "name": "Generated Address",
        "address": address,
        "city": city,
        "state": state,
        "zip_code": zipcode
    }

def search_yelp_for_address(zipcode):
    url = "https://api.yelp.com/v3/businesses/search"
    # API_KEY imported from config at top of file
    headers = {"accept": "application/json", "Authorization": f"Bearer {API_KEY}"}
    params = {"location": zipcode, "sort_by": "distance", "limit": 50}
        
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        js = response.json()
        bus = _(js, "businesses")
                
        if not bus:
            return None
                    
        valid_bus = []
        for b in bus:
            zip_code = _(b, "location.zip_code")
            if zip_code == zipcode:
                address = _(b, "location.address1") or _(b, "location.address2") or _(b, "location.address3") or ""
                if address and len(address.strip()) >= 5:
                    valid_bus.append({
                        "name": _(b, "name"),
                        "location": {
                            "address": address.strip(),
                            "city": _(b, "location.city"),
                            "state": _(b, "location.state"),
                            "zip_code": zip_code
                        }
                    })
                
        if not valid_bus:
            print("❌ No valid businesses with proper addresses found.")
            return None
                
        chosen = random.choice(valid_bus)
        return {
            "name": chosen["name"],
            "address": chosen["location"]["address"],
            "city": chosen["location"]["city"],
            "state": chosen["location"]["state"],
            "zip_code": chosen["location"]["zip_code"]
        }
        
    except Exception as e:
        print(f"❌ Error searching Yelp: {e}")
        return None

def get_address_option():
    """Ask user whether they want real or fake address"""
    previous_type = storage.get_previous_address_type()
    
    while True:
        if previous_type:
            type_name = 'Real (Yelp)' if previous_type == 'R' else 'Fake (Generated)'
            print(f"Previous: {type_name}")
            choice = input("(R)eal or (F)ake address? (Enter=use previous, 'b'=back): ").strip().upper()
        else:
            choice = input("(R)eal or (F)ake address? ('b'=back): ").strip().upper()
        
        if choice == 'B':
            raise BackStep()
        elif choice == '' and previous_type:
            storage.save_address_type(previous_type)
            return previous_type
        elif choice in ['R', 'F']:
            storage.save_address_type(choice)
            return choice
        print("Please enter 'R' for real or 'F' for fake address.")

def _normalize_address_choice(choice):
    """Normalize address choice inputs to the legacy R/F values."""
    if choice is None:
        return None

    normalized = str(choice).strip().upper()
    if normalized in ["R", "REAL", "YELP"]:
        return "R"
    if normalized in ["F", "FAKE", "GENERATED"]:
        return "F"
    return None

def get_address(zipcode, choice=None, allow_fallback_prompt=True):

    """Main function to get address based on user preference"""
    normalized_choice = _normalize_address_choice(choice)
    if normalized_choice:
        storage.save_address_type(normalized_choice)
    else:
        normalized_choice = get_address_option()
    
    if normalized_choice == 'F':
        print("🏠 Generating fake address...")
        return generate_fake_address(zipcode)
    else:
        print("🔍 Searching for real address from Yelp...")
        real_address = search_yelp_for_address(zipcode)
        
        if real_address is None:
            if not allow_fallback_prompt:
                print("⚠️  No real addresses found. Falling back to a generated address.")
                return generate_fake_address(zipcode)
            print("⚠️  No real addresses found. Would you like a fake address instead? (Y/N, or 'b' to go back): ", end="")
            fallback = input().strip().upper()
            if fallback == 'B':
                raise BackStep()
            if fallback == 'Y':
                print("🏠 Generating fake address as fallback...")
                return generate_fake_address(zipcode)
            else:
                return None
        
        return real_address

def auto_fill_from_zip(zip_code):
    """
    Given a ZIP code, return city and state information
    
    Args:
        zip_code: 5-digit ZIP code string
        
    Returns:
        dict with 'city', 'state', and 'zip' keys
    """
    try:
        import requests
        
        # Use free ZIP code API
        response = requests.get(f'https://api.zippopotam.us/us/{zip_code}', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'city': data['places'][0]['place name'].upper(),
                'state': data['places'][0]['state abbreviation'],
                'zip': zip_code
            }
    except Exception as e:
        print(f"⚠️ Could not look up ZIP {zip_code}: {e}")
    
    # Fallback if lookup fails
    return {
        'city': 'ANYTOWN',
        'state': 'ST',
        'zip': zip_code
    }
