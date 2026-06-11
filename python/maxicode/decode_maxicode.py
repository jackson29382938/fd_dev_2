import subprocess
import re
import random
import string
import os
import ctypes
import sys
import requests  # Need to install: pip install requests
from urllib.parse import quote_plus

# Import settings manager and debug flag
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ftid_gen.settings_manager import settings
    from ftid_gen.config import (
        DEBUG,
        BASE_DIR as CONFIG_BASE_DIR,
        BARCODES_DIR as CONFIG_BARCODES_DIR,
    )
    # ZXing JAR paths are optional — only needed for interactive decode mode.
    try:
        from ftid_gen.config import (
            ZXING_CORE_JAR_PATH as CONFIG_ZXING_CORE_JAR_PATH,
            ZXING_JAVASE_JAR_PATH as CONFIG_ZXING_JAVASE_JAR_PATH,
            JCOMMANDER_JAR_PATH as CONFIG_JCOMMANDER_JAR_PATH,
        )
    except ImportError:
        CONFIG_ZXING_CORE_JAR_PATH = None
        CONFIG_ZXING_JAVASE_JAR_PATH = None
        CONFIG_JCOMMANDER_JAR_PATH = None
except ImportError:
    settings = None
    DEBUG = False
    CONFIG_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_BARCODES_DIR = None
    CONFIG_ZXING_CORE_JAR_PATH = None
    CONFIG_ZXING_JAVASE_JAR_PATH = None
    CONFIG_JCOMMANDER_JAR_PATH = None

ROOT_DIR = os.fspath(CONFIG_BASE_DIR)
MAXICODE_DIR = os.path.join(ROOT_DIR, "maxicode")
REQUIREMENTS_DIR = os.path.join(ROOT_DIR, "requirements")
DEFAULT_IMAGE_PATH = os.path.join(MAXICODE_DIR, "assets", "working.png")

def debug_print(*args, **kwargs):
    """Print only if DEBUG mode is enabled"""
    if DEBUG:
        print(*args, **kwargs)

# Try to import zint, but make it optional
ZINT_AVAILABLE = False
try:
    if sys.platform == "darwin":
        from zint import Symbol, Symbology
        ZINT_AVAILABLE = True
    elif sys.platform == "win32":
        if os.path.exists(os.path.join(REQUIREMENTS_DIR, "zint.exe")):
            ZINT_AVAILABLE = True
except ImportError as e:
    debug_print(f"Zint not available: {e}")
    ZINT_AVAILABLE = False
except OSError as e:
    debug_print(f"Zint library error: {e}")
    ZINT_AVAILABLE = False

# === CONFIG ===
ZXING_STANDALONE_JAR_PATH = os.environ.get(
    "ZXING_STANDALONE_JAR_PATH",
    os.path.join(MAXICODE_DIR, "jar-files", "javase-3.5.3-jar-with-dependencies.jar"),
)
ZXING_CORE_JAR_PATH = CONFIG_ZXING_CORE_JAR_PATH or os.path.join(MAXICODE_DIR, "jar-files", "core-3.5.0.jar")
ZXING_JAVASE_JAR_PATH = CONFIG_ZXING_JAVASE_JAR_PATH or os.path.join(MAXICODE_DIR, "jar-files", "javase-3.5.0.jar")
JCOMMANDER_JAR_PATH = CONFIG_JCOMMANDER_JAR_PATH or os.path.join(MAXICODE_DIR, "jar-files", "jcommander-1.82.jar")

# Output directory - use config for proper path in bundled apps
try:
    BARCODES_DIR = str(CONFIG_BARCODES_DIR)
except Exception:
    BARCODES_DIR = os.path.join(os.getcwd(), "barcodes")
    os.makedirs(BARCODES_DIR, exist_ok=True)
OUTPUT_IMAGE = os.path.join(BARCODES_DIR, "modified_maxicode.png")

TARGET_LENGTH = 80  # Total desired length of the data (legacy; not used for cap)
UPS_SEGMENT_LENGTH = 18  # "UPS" + 9 characters = 12 total characters to keep
MAX_MAXICODE_LENGTH = 70  # Hard cap for final MaxiCode string length
NON_INTERACTIVE = (
    os.environ.get("FTID_NONINTERACTIVE", "").lower() in ("1", "true", "yes")
    or not sys.stdin.isatty()
)


class NonInteractivePromptError(RuntimeError):
    pass


def _noninteractive_prompt_error(prompt):
    return NonInteractivePromptError(
        f"Cannot prompt for input while running from the macOS app: {prompt}"
    )

# === HELPER FUNCTIONS ===
def get_user_choice(prompt, valid_choices, default=None):
    """Get user choice with validation."""
    if NON_INTERACTIVE:
        if default in valid_choices:
            return default
        raise _noninteractive_prompt_error(prompt)

    while True:
        choice = input(prompt).strip().lower()
        if choice in valid_choices:
            return choice
        print(f"Invalid choice. Please enter one of: {', '.join(valid_choices)}")

def get_image_path():
    """Get image path from user with validation."""
    if NON_INTERACTIVE:
        if os.path.exists(DEFAULT_IMAGE_PATH):
            return DEFAULT_IMAGE_PATH
        raise _noninteractive_prompt_error("Enter the path to your MaxiCode image")

    while True:
        image_path = input("Enter the path to your MaxiCode image: ").strip()
        if image_path =='1':
            image_path = DEFAULT_IMAGE_PATH
        if os.path.exists(image_path):
            return image_path
        print(f"File not found: {image_path}")
        retry = get_user_choice("Would you like to try again? (y/n): ", ['y', 'n'])
        if retry == 'n':
            return None

def get_input_choice():
    """Get user choice for input method; Enter defaults to create from scratch."""
    # Check settings to see if we should skip the prompt
    if NON_INTERACTIVE or (settings and not settings.get('maxicode.prompt_input_method', False)):
        # Skip prompt, default to create from scratch for bulk processing
        return '2'

    print("\n=== INPUT METHOD ===")
    print("Choose how you want to provide MaxiCode data:")
    print("1. Decode from existing MaxiCode image")
    print("2. Create MaxiCode data from scratch")

    while True:
        raw = input("Press Enter to create from scratch, or type 1 to decode: ").strip()
        if raw == '':
            return '2'
        if raw in ['1', '2']:
            return raw
        print("Invalid choice. Press Enter for create-from-scratch or type 1/2.")

def create_maxicode_from_scratch():
    """Create MaxiCode data from scratch using previously inputted data."""
    print("\n=== CREATE MAXICODE FROM SCRATCH ===")

    # Import data storage to get previous inputs
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ftid_gen.data_storage import storage
    from ftid_gen.address_utils import auto_fill_from_zip

    # Get ZIP code from previous data
    zip_code = storage.get_previous('receiver_zip') or storage.get_previous('sender_zip')
    if not zip_code or len(zip_code) != 5 or not zip_code.isdigit():
        zip_code = ''.join(random.choices(string.digits, k=5))
    else:
        pass

    # Auto-calculate city and state from ZIP
    city = None
    state = None
    if zip_code:
        location_info = auto_fill_from_zip(zip_code)
        if location_info:
            city = location_info['city'].upper()
            state = location_info['state'].upper()


    if not city:
        cities = ["NEW YORK", "LOS ANGELES", "CHICAGO", "HOUSTON", "PHOENIX", "PHILADELPHIA",
                 "SAN ANTONIO", "SAN DIEGO", "DALLAS", "SAN JOSE", "AUSTIN", "JACKSONVILLE"]
        city = random.choice(cities)


    if not state:
        states = ["NY", "CA", "IL", "TX", "AZ", "PA", "FL", "NV", "WA", "OR", "CO", "GA"]
        state = random.choice(states)


    # Get tracking number from previous data
    tracking_number = (storage.get_previous('ups_tracking') or
                      storage.get_previous('usps_tracking') or
                      storage.get_previous('fedex_tracking'))
    if not tracking_number:
        tracking_number = "1Z" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    else:
        pass

    # Set defaults for other fields
    country_code = "840"
    service_class = "001"
    scac = "UPSN"

    # Generate shipper number
    shipper_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # Generate package weight
    package_weight = '001'



    # Build MaxiCode data string
    # Format: [)>\x1e01\x1dZIPCODE\x1dCOUNTRY\x1dSERVICE\x1dTRACKING\x1dSCAC\x1dSHIPPER\x1dWEIGHT\x1d...\x1dCITY\x1dSTATE\x1e\x04

    # Use ASCII control characters
    rs_char = chr(30)  # Record Separator (\x1e)
    gs_char = chr(29)  # Group Separator (\x1d)
    eot_char = chr(4)  # End of Transmission (\x04)

    # Additional random fields to fill space (NO CHARACTER LIMITS)
    random_field1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    random_field2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    random_field3 = '1/1'  # Package sequence
    random_field4 = ''.join(random.choices(string.digits, k=3))

    # Extended fields for unlimited data
    extended_field1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    extended_field2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    extended_field3 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    # Construct the MaxiCode data; will cap later to MAX_MAXICODE_LENGTH
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

def get_manual_data():
    """Get manual data input from user."""
    if NON_INTERACTIVE:
        raise _noninteractive_prompt_error("Please enter the MaxiCode data")

    print("\n=== MANUAL DATA INPUT ===")
    print("Here are some options to get MaxiCode data manually:")
    print("1. Website: https://products.aspose.app/barcode/recognize#")
    print("2. Text cleaner: https://textcleaner.net/")
    print("3. Or enter the data directly if you have it")

    while True:
        manual_data = input("\nPlease enter the MaxiCode data: ").strip()
        if manual_data:
            return manual_data
        print("Data cannot be empty. Please try again.")

# === STEP 1: Decode MaxiCode using ZXing ===
def decode_maxicode_zxing(image_path):
    """Decode MaxiCode using ZXing command line tool with retry options."""
    if not image_path or not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return get_manual_data()

    # Use standalone JAR if available, otherwise use separate JARs
    if os.path.exists(ZXING_STANDALONE_JAR_PATH):
        classpath = ZXING_STANDALONE_JAR_PATH
    else:
        # Fallback to separate JARs
        if not os.path.exists(ZXING_JAVASE_JAR_PATH) or not os.path.exists(ZXING_CORE_JAR_PATH):
            print("ERROR: ZXing JARs not found.")
            return get_manual_data()

        separator = ";" if os.name == 'nt' else ":"
        classpath_parts = [ZXING_CORE_JAR_PATH, ZXING_JAVASE_JAR_PATH]

        if os.path.exists(JCOMMANDER_JAR_PATH):
            classpath_parts.append(JCOMMANDER_JAR_PATH)

        classpath = separator.join(classpath_parts)

    try:

        result = subprocess.run(
            ['java', '-cp', classpath, 'com.google.zxing.client.j2se.CommandLineRunner', image_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30  # Add timeout to prevent hanging
        )

        if result.returncode != 0:
            return handle_decode_failure(image_path)

        output = result.stdout.strip()
        if not output:
            return handle_decode_failure(image_path)

        # Extract the decoded data from "Parsed result:" line
        lines = output.split('\n')
        decoded_data = None

        for line in lines:
            if line.startswith("Parsed result:"):
                # Extract everything after "Parsed result:"
                decoded_data = line.replace("Parsed result:", "").strip()
                break

        if not decoded_data:
            # Fallback: look for lines that contain "UPS"
            for line in lines:
                if "UPS" in line and not line.startswith("Found"):
                    decoded_data = line.strip()
                    break

        if not decoded_data:
            return handle_decode_failure(image_path)



        return decoded_data

    except subprocess.TimeoutExpired:
        print("ZXing command timed out.")
        return handle_decode_failure(image_path)
    except Exception as e:
        print(f"Failed to decode with ZXing: {e}")
        return handle_decode_failure(image_path)

def handle_decode_failure(original_image_path):
    """Handle decoding failure with retry options."""
    if NON_INTERACTIVE:
        raise RuntimeError(
            f"Could not decode MaxiCode image non-interactively: {original_image_path}"
        )

    print("\nDecoding failed. Options:")
    print("1. Try a different image")
    print("2. Enter data manually")
    print("3. Retry with the same image")

    choice = get_user_choice("Enter your choice (1/2/3): ", ['1', '2', '3'])

    if choice == '1':
        new_image_path = get_image_path()
        if new_image_path:
            return decode_maxicode_zxing(new_image_path)
        else:
            return get_manual_data()
    elif choice == '2':
        return get_manual_data()
    elif choice == '3':
        return decode_maxicode_zxing(original_image_path)

# === STEP 2: Modify MaxiCode data with NO CHARACTER LIMITS ===
def generate_random_string(length):
    """Generate a random string of specified length using alphanumeric characters."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def modify_maxicode_data(data):
    """
    Modify MaxiCode data to preserve ALL original data and append extended fields.
    NO CHARACTER LIMITS - uses all available data plus additional extensions.
    """
    while True:
        try:
            # Find the start of the MaxiCode header "[)>"
            header_match = re.search(r"\[\)>", data)
            if not header_match:
                print("Invalid MaxiCode data: missing header.")
                if NON_INTERACTIVE:
                    raise ValueError("Could not find '[)>' in the data")
                choice = get_user_choice("Would you like to (1) enter new data or (2) continue anyway? (1/2): ", ['1', '2'])
                if choice == '1':
                    data = get_manual_data()
                    continue
                else:
                    raise ValueError("Could not find '[)>' in the data")

            # Find 'UPS' (case-sensitive, as it should appear in all-caps)
            ups_match = re.search(r"UPS", data)
            if not ups_match:
                print("Invalid MaxiCode data: missing 'UPS'.")
                if NON_INTERACTIVE:
                    raise ValueError("Could not find 'UPS' in the data")
                choice = get_user_choice("Would you like to (1) enter new data or (2) continue anyway? (1/2): ", ['1', '2'])
                if choice == '1':
                    data = get_manual_data()
                    continue
                else:
                    raise ValueError("Could not find 'UPS' in the data")

            # Extract ALL data from [)> to the end (NO CHARACTER LIMITS)
            start_index = header_match.start()

            # Use ALL remaining data after the header
            preserved_segment = data[start_index:]



            # Add extended data without any limits
            random_suffix = generate_random_string(20)  # Additional random data
            gs_char = chr(29)  # Group Separator
            rs_char = chr(30)  # Record Separator
            eot_char = chr(4)  # End of Transmission

            # Build enhanced data with ALL original data plus extensions
            modified_data = (
                f"{preserved_segment}"      # ALL original data
                f"{gs_char}"                # Group separator
                f"EXT{random_suffix}"       # Extended data
                f"{rs_char}"                # Record separator
                f"{eot_char}"               # End of transmission
            )

            # Enforce 144-character cap and ensure it ends with EOT
            if len(modified_data) > MAX_MAXICODE_LENGTH:
                modified_data = modified_data[:MAX_MAXICODE_LENGTH]
            # Ensure last character is EOT
            if not modified_data or modified_data[-1] != eot_char:
                if len(modified_data) >= 1:
                    modified_data = modified_data[:-1] + eot_char
                else:
                    modified_data = eot_char


            print(f"📏 Final modified data length (capped to {MAX_MAXICODE_LENGTH}): {len(modified_data)} characters")
            print(f"🔤 Enhanced Maxicode data: {repr(modified_data)}")

            return modified_data

        except Exception as e:
            print(f"❌ Error modifying data: {e}")
            if NON_INTERACTIVE:
                raise
            choice = get_user_choice("Would you like to (1) enter new data or (2) abort? (1/2): ", ['1', '2'])
            if choice == '1':
                data = get_manual_data()
                continue
            else:
                raise

# --- TEC-IT Configuration (Constants for Online Method) ---
TEC_IT_BASE_URL = "https://barcode.tec-it.com/barcode.ashx"

def encode_maxicode_tec_it(data, output_path):
    """
    Encodes data as MaxiCode using the TEC-IT web service (online method).

    Args:
        data (str): The combined MaxiCode data (Primary + Group Separator + Secondary).
        output_path (str): The local path to save the resulting image file.

    Returns:
        bool: True on success.

    Raises:
        RuntimeError: If the web request fails or returns a non-200 status.
    """
    print("--- ONLINE METHOD: Using TEC-IT Barcode Generator ---")


    # 1. URL Encode the Data
    # Use Group Separator (ASCII 29) to delimit data, URL-encoded as %1D
    #limit data to 93 characters
    if len(data) > 60:
        data = data[:60]
        #test length of data
        length = len(data)
        debug_print(f" Length of data: {length}")
    debug_print(f" Encoded data: {data}")
    ENCODED_DATA = quote_plus(data)

        # 2. Assemble Request Parameters
    params = {
        "data": ENCODED_DATA,
        "code": "MaxiCode", # Set the symbology
        "eclevel": "500",    # Common error correction level for MaxiCode
        "unit": "mil",       # Unit for dimensions
        "dpi": "300"         # Resolution
    }

    # 3. Execute the GET request
    try:
        response = requests.get(TEC_IT_BASE_URL, params=params, timeout=15)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)

        # 4. Save the image content
        if response.status_code == 200:
            with open(output_path, 'wb') as file:
                file.write(response.content)
            print(f"SUCCESS: Online MaxiCode image saved to {output_path}")
            return True
        else:
            raise RuntimeError(f"Online service returned unexpected status code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        # Catch network errors, timeouts, and HTTP errors (4xx/5xx)
        raise RuntimeError(f"Online service request failed: {e}")

# --- Helper function for Zint CLI (Simplified from your original) ---
def encode_maxicode_zint_cli(data, output_path):
    """Helper for Windows Zint CLI (used as a fallback for the new primary Windows method)."""
    ZINT_EXE_PATH = os.path.join(REQUIREMENTS_DIR, "zint.exe")
    print(f"WINDOWS/CLI: Zint executable path: {ZINT_EXE_PATH}")
    cmd = [
        ZINT_EXE_PATH,
        "-b", "141",
        "-o", output_path,
        "-d", data,
        "--scale=2.0",
        "--border=0",
        "--dotty",
        "--dotsize=0.8"
    ]

    print(f"WINDOWS/CLI: Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Zint CLI error: {result.stderr.strip()}")
    return True

# --- Main Encoding Function ---
def encode_maxicode(data, output_path, scale_override=None):
    """
    Encode data as MaxiCode using the pure-Python encoder.

    This replaces the previous multi-method approach (ZXing Java, Zint CLI,
    TEC-IT online) with a single pure-Python implementation that has no
    external dependencies beyond PIL.

    Args:
        data: MaxiCode data string.
        output_path: Output image path.
        scale_override: Optional scale multiplier (default 2).
    """
    from maxicode.pure_maxicode import encode_maxicode as _pure_encode

    scale = scale_override if scale_override is not None else 2.0
    try:
        _pure_encode(data, output_path, scale_override=scale)
        return True
    except Exception as e:
        print(f"Failed to encode MaxiCode: {e}")
        if NON_INTERACTIVE:
            raise RuntimeError(f"Failed to encode MaxiCode non-interactively: {e}") from e
        print("Choose an option:")
        print("1. Try different output filename")
        print("2. Retry with same settings")
        print("3. Abort encoding")
        choice = input("Enter your choice (1/2/3): ").strip()
        if choice == '1':
            new_output = input("Enter new output filename: ").strip()
            if new_output:
                output_path = new_output
            return encode_maxicode(data, output_path, scale_override=scale_override)
        elif choice == '2':
            return encode_maxicode(data, output_path, scale_override=scale_override)
        elif choice == '3':
            raise RuntimeError(f"Encoding aborted by user: {e}")


def validate_config():
    """Validate configuration before running."""
    errors = []
    warnings = []

    if TARGET_LENGTH <= UPS_SEGMENT_LENGTH:
        errors.append(f"Target length ({TARGET_LENGTH}) must be greater than UPS segment length ({UPS_SEGMENT_LENGTH})")

    if warnings:
        for warning in warnings:
            print(f"WARNING: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("Note: If ZXing JARs are missing, you can still input data manually.")
        return False

    return True

def generate_maxicode_image(output_path=OUTPUT_IMAGE, scale_override=None):
    """Create a MaxiCode image from stored FTID data without prompting."""
    print("=== MaxiCode Decoder/Modifier/Encoder ===")

    # Validate configuration
    config_valid = validate_config()

    if not config_valid:
        print("Configuration warnings were reported; continuing with available encoders.")

    print("\n=== STEP 2: CREATING DATA ===")
    original_data = create_maxicode_from_scratch()
    if not original_data:
        raise RuntimeError("No MaxiCode data could be created.")

    print(f"Original data: {repr(original_data)}")

    print("\n=== STEP 3: MODIFYING DATA ===")
    modified_data = modify_maxicode_data(original_data)

    print(f"Modified data: {repr(modified_data)}")

    print("\n=== STEP 4: ENCODING ===")
    if len(modified_data) > MAX_MAXICODE_LENGTH:
        print(f"Modified data exceeds {MAX_MAXICODE_LENGTH} characters. Truncating.")
        modified_data = modified_data[:MAX_MAXICODE_LENGTH]

    encode_maxicode(modified_data, output_path, scale_override=scale_override)

    print("\n=== SUCCESS ===")
    print(f"Modified MaxiCode saved as: {output_path}")
    print(f"Original data length: {len(original_data)} characters")
    print(f"Modified data length: {len(modified_data)} characters")
    return output_path


# === MAIN ===
def main():
    """Main execution function with comprehensive retry options."""
    print("=== MaxiCode Decoder/Modifier/Encoder ===")

    # Validate configuration
    config_valid = validate_config()

    # Get input method choice
    print("\n=== STEP 1: INPUT METHOD ===")
    input_choice = get_input_choice()

    try:
        if input_choice == '1':
            # Original workflow: decode from image
            print("\n=== STEP 1A: INPUT IMAGE ===")
            image_path = get_image_path()

            print("\n=== STEP 2: DECODING ===")
            original_data = decode_maxicode_zxing(image_path)
            if not original_data:
                print("No data obtained. Exiting.")
                return
        else:
            # New workflow: create from scratch
            print("\n=== STEP 2: CREATING DATA ===")
            original_data = create_maxicode_from_scratch()
            if not original_data:
                print("No data created. Exiting.")
                return

        print(f"Original data: {repr(original_data)}")

        print("\n=== STEP 3: MODIFYING DATA ===")
        modified_data = modify_maxicode_data(original_data)
        #modified_data = original_data




        print(f"Modified data: {repr(modified_data)}")

        #
        print("\n=== STEP 4: ENCODING ===")
        # Fixed: Don't use repr() when encoding - pass the actual string
        #ensure data is less than 93 characters
        if len(modified_data) > MAX_MAXICODE_LENGTH:
            print(f"Modified data exceeds {MAX_MAXICODE_LENGTH} characters. Truncating.")
            modified_data = modified_data[:MAX_MAXICODE_LENGTH]

        encode_maxicode(modified_data, OUTPUT_IMAGE)

        print("\n=== SUCCESS ===")
        print(f"Modified MaxiCode saved as: {OUTPUT_IMAGE}")
        print(f"Original data length: {len(original_data)} characters")
        print(f"Modified data length: {len(modified_data)} characters")

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\n=== ERROR ===")
        print(f"Operation failed: {e}")
        if NON_INTERACTIVE:
            raise

        # Offer to retry the entire process
        retry = get_user_choice("Would you like to start over? (y/n): ", ['y', 'n'])
        if retry == 'y':
            main()

if __name__ == "__main__":
    main()
