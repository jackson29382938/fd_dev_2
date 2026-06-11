
import os
import sys
from pathlib import Path

# Application version
VERSION = "2.0.0"

# Debug mode - default False for clean output
# Set FTID_DEBUG=1 environment variable to enable debug output
DEBUG = os.environ.get('FTID_DEBUG', '').lower() in ('1', 'true', 'yes')

# Environment helpers
def _get_env(name, default=None):
    return os.environ.get(name, default)

def get_base_path():
    """Get the base path that works both in development and when packaged with PyInstaller."""
    env_base_path = _get_env("FTID_BASE_DIR")
    if env_base_path:
        return Path(env_base_path)

    if getattr(sys, 'frozen', False):
        # Running as compiled executable - files are in the temp directory
        return Path(sys._MEIPASS)
    else:
        # Running as script - go one parent up from the script location
        return Path(__file__).parent.parent

def get_output_path():
    """Get a writable output path for generated files."""
    env_output_dir = _get_env("FTID_OUTPUT_DIR")
    if env_output_dir:
        output_dir = Path(env_output_dir)
    elif getattr(sys, 'frozen', False):
        # Running as compiled executable - use user's Documents folder
        output_dir = Path.home() / "Documents" / "FTID_Generator"
    else:
        # Running as script - use project directory
        output_dir = Path(__file__).parent.parent

    # Ensure output directories exist
    (output_dir / "barcodes").mkdir(parents=True, exist_ok=True)
    (output_dir / "progress").mkdir(parents=True, exist_ok=True)
    (output_dir / "requirements").mkdir(parents=True, exist_ok=True)
    return output_dir

# Get the base directory (for bundled resources)
BASE_DIR = get_base_path()
SCRIPT_DIR = Path(__file__).parent

# Load environment variables from the project-local .env file when it exists.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass  # python-dotenv not installed, use system env vars

# Get the output directory (for writable files)
OUTPUT_DIR = get_output_path()

# Optional state directory used by the macOS app bridge for config/history files.
STATE_DIR = Path(_get_env("FTID_STATE_DIR", str(OUTPUT_DIR)))

# Define all file paths - use OUTPUT_DIR for writable files
CSV_LOG_PATH = OUTPUT_DIR / "requirements" / "label_history.csv"
ZIPCODE_FILE = BASE_DIR / "requirements" / "zipcodes.json"
FONT_MAIN = BASE_DIR / "requirements" / "NotoSans-ExtraCondensedSemiBold.ttf"
FONT_BOLD = BASE_DIR / "requirements" / "NotoSans-CondensedBold.ttf"
FONT_ARIAL = BASE_DIR / "requirements" / "ARIAL.ttf"

# Barcodes and progress directories (must be writable)
BARCODES_DIR = OUTPUT_DIR / "barcodes"
PROGRESS_DIR = OUTPUT_DIR / "progress"

# Third-party API keys (set YELP_API_KEY in environment or .env for real-address lookup)
API_KEY = _get_env("YELP_API_KEY", "")

# FedEx 96-tracking prefix (GS1 Application Identifier 00)
FEDEX_TRACKING_PREFIX = "9632013760204789920400"

# MaxiCode encoding is now handled by the pure-Python encoder (maxicode/pure_maxicode.py).
# No external Java/JAR dependencies required.



TEMPLATES = {
    "1": ("USPS_GS1", "(420)85206(94)000373170096969320", "ftid_gen/templates/usps/template/usps_temp_blank.png"),
    "2": ("UPS_Code128", "1ZAC66060378780311", "ftid_gen/templates/ups/template/ups_temp_blank.png"),
    "3": ("FedEx_96", f"{FEDEX_TRACKING_PREFIX}791767518101", "ftid_gen/templates/fedex/template/fedex_temp_blank.png"),
    "4": ("FTID_UPS", None, "ftid_gen/templates/ups/template/ups_temp_blank.png"),
    "5": ("FTID_USPS", None, "ftid_gen/templates/usps/template/usps_temp_blank.png"),
    "6": ("FTID_FEDEX", None, "ftid_gen/templates/fedex/template/fedex_temp_blank.png")
}

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Charles", "Joseph", "Thomas",
    "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Jason", "Edward", "Jeffrey", "Ryan",
    "Jacob", "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon",
    "Benjamin", "Samuel", "Gregory", "Alexander", "Patrick", "Frank", "Raymond", "Jack", "Dennis", "Jerry",
    "Tyler", "Aaron", "Jose", "Henry", "Adam", "Douglas", "Nathan", "Peter", "Zachary", "Kyle",
    "Noah", "Alan", "Ethan", "Jeremy", "Lionel", "Angel", "Wayne", "Carl", "Harold", "Jordan",
    "Jesse", "Arthur", "Lawrence", "Sean", "Christian", "Austin", "Joe", "Eli", "Albert", "Wayne",
    "Mason", "Roy", "Ralph", "Eugene", "Louis", "Philip", "Johnny", "Mason", "Jason", "Carl",
    "Emma", "Olivia", "Ava", "Isabella", "Sophia", "Charlotte", "Mia", "Amelia", "Harper", "Evelyn",
    "Abigail", "Emily", "Elizabeth", "Mila", "Ella", "Avery", "Sofia", "Camila", "Aria", "Scarlett",
    "Victoria", "Madison", "Luna", "Grace", "Chloe", "Penelope", "Layla", "Riley", "Zoey", "Nora",
    "Lily", "Eleanor", "Hannah", "Lillian", "Addison", "Aubrey", "Ellie", "Stella", "Natalie", "Zoe",
    "Leah", "Hazel", "Violet", "Aurora", "Savannah", "Audrey", "Brooklyn", "Bella", "Claire", "Skylar",
    "Lucy", "Paisley", "Everly", "Anna", "Caroline", "Nova", "Genesis", "Emilia", "Kennedy", "Samantha",
    "Maya", "Willow", "Kinsley", "Naomi", "Aaliyah", "Elena", "Sarah", "Ariana", "Allison", "Gabriella",
    "Alice", "Madelyn", "Cora", "Ruby", "Eva", "Serenity", "Autumn", "Adeline", "Hailey", "Gianna",
    "Valentina", "Isla", "Eliana", "Quinn", "Nevaeh", "Ivy", "Sadie", "Piper", "Lydia", "Alexa",
    "Josephine", "Emery", "Julia", "Delilah", "Arianna", "Vivian", "Kaylee", "Sophie", "Brielle", "Madeline"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor",
    "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Robinson",
    "Clark", "Rodriguez", "Lewis", "Lee", "Walker", "Hall", "Allen", "Young", "Hernandez", "King",
    "Wright", "Lopez", "Hill", "Scott", "Green", "Adams", "Baker", "Gonzalez", "Nelson", "Carter",
    "Mitchell", "Perez", "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins",
    "Stewart", "Sanchez", "Morris", "Rogers", "Reed", "Cook", "Morgan", "Bell", "Murphy", "Bailey",
    "Rivera", "Cooper", "Richardson", "Cox", "Howard", "Ward", "Torres", "Peterson", "Gray", "Ramirez",
    "Watson", "Brooks", "Kelly", "Sanders", "Price", "Bennett", "Wood", "Barnes", "Ross", "Henderson",
    "Coleman", "Jenkins", "Perry", "Powell", "Long", "Patterson", "Hughes", "Flores", "Washington", "Butler",
    "Simmons", "Foster", "Gonzales", "Bryant", "Alexander", "Russell", "Griffin", "Diaz", "Hayes", "Myers",
    "Ford", "Hamilton", "Graham", "Sullivan", "Wallace", "Woods", "Cole", "West", "Jordan", "Owens",
    "Reynolds", "Fisher", "Ellis", "Harrison", "Gibson", "Mcdonald", "Cruz", "Marshall", "Ortiz", "Gomez",
    "Murray", "Freeman", "Wells", "Webb", "Simpson", "Stevens", "Tucker", "Porter", "Hunter", "Hicks",
    "Crawford", "Henry", "Boyd", "Mason", "Morales", "Kennedy", "Warren", "Dixon", "Ramos", "Reyes",
    "Burns", "Gordon", "Shaw", "Holmes", "Rice", "Robertson", "Hunt", "Black", "Daniels", "Palmer",
    "Mills", "Nichols", "Grant", "Knight", "Ferguson", "Rose", "Stone", "Hawkins", "Dunn", "Perkins",
    "Hudson", "Spencer", "Gardner", "Stephens", "Payne", "Pierce", "Berry", "Matthews", "Arnold", "Wagner",
    "Willis", "Ray", "Watkins", "Olson", "Carroll", "Duncan", "Snyder", "Hart", "Cunningham", "Bradley",
    "Lane", "Andrews", "Ruiz", "Harper", "Fox", "Riley", "Armstrong", "Carpenter", "Weaver", "Greene",
    "Lawrence", "Elliott", "Chavez", "Sims", "Austin", "Peters", "Kelley", "Franklin", "Lawson", "Fields"
]
