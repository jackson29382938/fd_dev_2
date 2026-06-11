import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import time
import random

from requirements.utils import resource_path
from user_tracking.credentials import credentials_error_message, resolve_credentials_path
from user_tracking.ip_utils import get_ip_info as _get_ip_info

# Setup logging
logger = logging.getLogger(__name__)

# Configuration
import os

# Get base directory (one folder back from current script)
BASE_DIR = Path(__file__).resolve().parent.parent

# Credentials file path
CREDENTIALS_PATH = BASE_DIR / "requirements" / "credentials.json"

# Constants
SUBSCRIPTION_SHEET_NAME = "FTID_APP_USERS"
MAX_LOGIN_ATTEMPTS = 3


class SubscriptionManager:
    """Manages user subscriptions and usage tracking via Google Sheets."""
    
    def __init__(self) -> None:
        self.client: Optional[gspread.Client] = None
        self.sheet: Optional[gspread.Worksheet] = None
        self.current_user_id: Optional[str] = None
        self.current_user_row: Optional[int] = None
        self.setup_google_sheets()
    
    def _execute_with_retry(self, func, *args, **kwargs):
        """Execute a Google Sheets API call with retries on transient errors."""
        max_attempts = 5
        backoff = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except (gspread.exceptions.APIError, requests.exceptions.RequestException) as e:
                is_transient = True
                if isinstance(e, gspread.exceptions.APIError):
                    is_transient = e.code == 429 or e.code >= 500
                
                if not is_transient or attempt == max_attempts:
                    raise
                
                sleep_time = backoff + random.uniform(0, 0.5)
                logger.warning(
                    "Google Sheets transient API error (code/type: %s) in %s (attempt %d/%d). Retrying in %.2fs...",
                    getattr(e, 'code', type(e).__name__), func.__name__, attempt, max_attempts, sleep_time
                )
                time.sleep(sleep_time)
                backoff *= 2.0

    def setup_google_sheets(self) -> None:
        """Initialize connection to Google Sheets."""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials_path = resolve_credentials_path(BASE_DIR)
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                str(credentials_path), scope
            )
            self.client = gspread.authorize(creds)
            self.sheet = self._execute_with_retry(
                lambda: self.client.open(SUBSCRIPTION_SHEET_NAME).sheet1
            )
            logger.info("Connected to subscription database")
            print("✅ Connected to subscription database")
        except FileNotFoundError:
            message = credentials_error_message(BASE_DIR)
            logger.error(message)
            print(f"❌ Error: {message}")
            raise
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error("Google Sheet '%s' not found", SUBSCRIPTION_SHEET_NAME)
            print(f"❌ Error: Google Sheet '{SUBSCRIPTION_SHEET_NAME}' not found")
            print("Please create the subscription sheet or check the name")
            raise
        except Exception as e:
            logger.exception("Error connecting to Google Sheets")
            print(f"❌ Error connecting to Google Sheets: {e}")
            raise
    
    def get_ip_info(self) -> Dict[str, str]:
        """Get detailed IP and location information."""
        return _get_ip_info()
    
    def authenticate_user(self):
        """
        Authenticate user and check their remaining runs
        Returns True if user is authorized, False otherwise
        """
        print("\n" + "="*50)
        print("🔐 SUBSCRIPTION AUTHENTICATION REQUIRED")
        print("="*50)
        
        max_attempts = 3
        attempts = 0
        
        while attempts < max_attempts:
            try:
                user_id = input("\nEnter your User ID: ").strip()
                passcode = input("Enter your Passcode: ").strip()
                
                if not user_id or not passcode:
                    print("❌ Please enter both User ID and Passcode")
                    attempts += 1
                    continue
                
                # Find user in the sheet
                user_data = self.find_user(user_id, passcode)
                
                if user_data is None:
                    print("❌ Invalid User ID or Passcode")
                    attempts += 1
                    if attempts < max_attempts:
                        print(f"Attempts remaining: {max_attempts - attempts}")
                    continue
                
                # Check remaining runs
                remaining_runs = user_data['remaining_runs']
                
                if remaining_runs <= 0:
                    print("❌ No remaining runs available for your account")
                    print("Please contact support to purchase additional runs")
                    return False
                
                # User is valid and has runs remaining
                print(f"✅ Authentication successful!")
                print(f"Welcome, User ID: {user_id}")
                print(f"Remaining runs: {remaining_runs}")
                
                # Store current user info for later use
                self.current_user_id = user_id
                self.current_user_row = user_data['row_number']
                
                # Create user sheet if it doesn't exist
                self.ensure_user_sheet_exists(user_id)
                
                print("\nProceeding to main application...")
                return True
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                sys.exit(0)
            except Exception as e:
                print(f"❌ Error during authentication: {e}")
                attempts += 1
        
        print(f"\n❌ Maximum login attempts ({max_attempts}) exceeded")
        print("Access denied. Please contact support if you need assistance.")
        return False
    
    def find_user(self, user_id, passcode):
        """
        Find user in the Google Sheet
        Expected sheet format:
        Column A: User ID
        Column B: Passcode  
        Column C: Remaining Runs
        """
        try:
            # Get all records from the sheet
            all_records = self._execute_with_retry(self.sheet.get_all_records)
            
            for idx, record in enumerate(all_records):
                # Handle different possible column names
                record_user_id = str(record.get('User ID', record.get('UserID', record.get('user_id', '')))).strip()
                record_passcode = str(record.get('Passcode', record.get('Password', record.get('passcode', '')))).strip()
                remaining_runs = record.get('Remaining Runs', record.get('RemainingRuns', record.get('remaining_runs', 0)))
                
                if record_user_id == user_id and record_passcode == passcode:
                    try:
                        remaining_runs = int(remaining_runs)
                    except (ValueError, TypeError):
                        remaining_runs = 0
                    
                    return {
                        'user_id': user_id,
                        'passcode': passcode,
                        'remaining_runs': remaining_runs,
                        'row_number': idx + 2  # +2 because sheets are 1-indexed and we skip header
                    }
            
            return None
            
        except Exception as e:
            print(f"❌ Error searching for user: {e}")
            return None
    
    def get_current_remaining_runs(self):
        """
        Get the current remaining runs for the authenticated user
        Returns the number of remaining runs, or 0 if there's an error
        """
        try:
            if not self.current_user_row:
                return 0
            
            cell_obj = self._execute_with_retry(
                lambda: self.sheet.cell(self.current_user_row, 3)
            )
            current_value = cell_obj.value
            try:
                return int(current_value)
            except (ValueError, TypeError):
                return 0
                
        except Exception as e:
            print(f"❌ Error checking remaining runs: {e}")
            return 0
    
    def check_runs_before_generation(self):
        """
        Check if user has runs remaining before allowing label generation
        Returns True if user can generate labels, False otherwise
        """
        remaining_runs = self.get_current_remaining_runs()
        
        if remaining_runs <= 0:
            print("\n" + "="*50)
            print("❌ INSUFFICIENT RUNS")
            print("="*50)
            print("You have 0 remaining runs in your account.")
            print("No labels can be generated until you purchase additional runs.")
            print("Please contact support to add more runs to your account.")
            print("="*50)
            return False
        
        print(f"✅ Runs available: {remaining_runs}")
        return True
    
    def ensure_user_sheet_exists(self, user_id):
        """
        Create a user-specific sheet if it doesn't exist
        """
        try:
            # Try to access the user's sheet
            try:
                user_sheet = self._execute_with_retry(
                    lambda: self.client.open(SUBSCRIPTION_SHEET_NAME).worksheet(user_id)
                )
                print(f"✅ User sheet '{user_id}' already exists")
            except gspread.exceptions.WorksheetNotFound:
                # Create user sheet if it doesn't exist
                print(f"📋 Creating new sheet for user: {user_id}")
                user_sheet = self._execute_with_retry(
                    lambda: self.client.open(SUBSCRIPTION_SHEET_NAME).add_worksheet(
                        title=user_id, rows="1000", cols="20"
                    )
                )
                
                # Add headers for user run tracking
                headers = [
                    "Timestamp", "Method", "Sender_Name", "Sender_Address", 
                    "Sender_City_State_Zip", "Receiver_Name", "Receiver_Address", 
                    "Receiver_City_State_Zip", "Modified_Tracking", "Original_Tracking",
                    "User_IP", "User_City", "User_Region", "User_Country", 
                    "User_Postal", "User_ISP", "User_Coordinates", "User_Timezone", 
                    "User_Approx_Address", "Session_Info"
                ]
                self._execute_with_retry(
                    lambda: user_sheet.append_row(headers, value_input_option="USER_ENTERED")
                )
                print(f"✅ Created user sheet '{user_id}' with headers")
                
        except Exception as e:
            print(f"❌ Warning: Could not create/verify user sheet: {e}")
    
    def deduct_run_and_log(self, ftid_info, method):
        """
        Deduct one run from the user's remaining runs AND log the detailed run info
        This should be called after a label is successfully generated
        """
        try:
            if not self.current_user_id or not self.current_user_row:
                print("❌ Warning: No current user session found")
                return False
            
            # Double-check runs before deducting (safety check)
            if not self.check_runs_before_generation():
                return False
            
            # First, deduct the run
            success = self.deduct_run()
            
            if success:
                # Then log the detailed run information
                self.log_detailed_run(ftid_info, method)
                print(f"✅ Run deducted and logged for user: {self.current_user_id}")
                
                # Show updated remaining runs
                remaining = self.get_current_remaining_runs()
                print(f"📊 Remaining runs: {remaining}")
                
                return True
            else:
                print("❌ Failed to deduct run")
                return False
                
        except Exception as e:
            print(f"❌ Error in deduct_run_and_log: {e}")
            return False
    
    def deduct_run(self):
        """
        Deduct one run from the user's remaining runs
        """
        try:
            # Get current value
            cell_obj = self._execute_with_retry(
                lambda: self.sheet.cell(self.current_user_row, 3)
            )
            current_value = cell_obj.value
            try:
                current_runs = int(current_value)
            except (ValueError, TypeError):
                current_runs = 0
            
            # Deduct one run
            new_runs = max(0, current_runs - 1)
            
            # Update the sheet
            self._execute_with_retry(
                lambda: self.sheet.update_cell(self.current_user_row, 3, new_runs)
            )
            
            print(f"📉 Run deducted. Remaining runs: {new_runs}")
            return True
            
        except Exception as e:
            print(f"❌ Warning: Could not update run count: {e}")
            return False
    
    def log_detailed_run(self, ftid_info, method):
        """
        Log detailed run information to the user's individual sheet
        """
        try:
            # Get user's individual sheet
            user_sheet = self._execute_with_retry(
                lambda: self.client.open(SUBSCRIPTION_SHEET_NAME).worksheet(self.current_user_id)
            )
            
            # Get IP and location info
            ip_info = self.get_ip_info()
            
            # Prepare the row data
            row_data = [
                datetime.now().isoformat(),  # Timestamp
                method,  # Method (FTID_UPS, FTID_USPS, FTID_FEDEX)
                ftid_info.get("sender", "N/A"),  # Sender Name
                ftid_info.get("sender_address", "N/A"),  # Sender Address
                ftid_info.get("sender_2nd_line", "N/A"),  # Sender City/State/Zip
                ftid_info.get("receiver", "N/A"),  # Receiver Name
                ftid_info.get("receiver_address", "N/A"),  # Receiver Address
                ftid_info.get("receiver_2nd_line", "N/A"),  # Receiver City/State/Zip
                ftid_info.get("tracking_number", "N/A"),  # Modified Tracking
                ftid_info.get("tracking_bar", ftid_info.get("tracking_number", "N/A")),  # Original Tracking
                ip_info["ip"],  # User IP
                ip_info["city"],  # User City
                ip_info["region"],  # User Region
                ip_info["country"],  # User Country
                ip_info["postal"],  # User Postal Code
                ip_info["org"],  # User ISP/Organization
                ip_info["loc"],  # User Coordinates
                ip_info["timezone"],  # User Timezone
                ip_info["approx_address"],  # User Approximate Address
                f"User: {self.current_user_id}"  # Session Info
            ]
            
            # Add the row to the user's sheet
            self._execute_with_retry(
                lambda: user_sheet.append_row(row_data, value_input_option="USER_ENTERED")
            )
            
            # Also log to the general FTID_Log sheet (existing functionality)
            self.log_to_general_sheet(ftid_info, method, ip_info)
            
            print(f"📝 Detailed run logged to user sheet: {self.current_user_id}")
            
        except Exception as e:
            print(f"❌ Warning: Could not log detailed run info: {e}")
    
    def log_to_general_sheet(self, ftid_info, method, ip_info):
        """
        Log to the general FTID_Log sheet (maintains existing functionality)
        """
        try:
            # Try to access the general log sheet
            try:
                log_sheet = self._execute_with_retry(
                    lambda: self.client.open("FTID_Log").sheet1
                )
            except gspread.exceptions.SpreadsheetNotFound:
                print("⚠️ General FTID_Log sheet not found, skipping general log")
                return
            
            # Extract zip codes
            sender_zip = ftid_info.get("sender_2nd_line", "").split()[-1] if ftid_info.get("sender_2nd_line") else "N/A"
            receiver_zip = ftid_info.get("receiver_2nd_line", "").split()[-1] if ftid_info.get("receiver_2nd_line") else "N/A"
            
            row = [
                datetime.now().isoformat(),
                ip_info["ip"],
                ip_info["city"],
                ip_info["region"],
                ip_info["country"],
                ip_info["postal"],
                ip_info["org"],
                ip_info["loc"],
                ip_info["timezone"],
                ip_info["approx_address"],
                sender_zip,
                receiver_zip,
                ftid_info.get("tracking_number", "N/A"),
                f"User: {self.current_user_id}",  # Add user ID to general log
                method
            ]
            
            self._execute_with_retry(
                lambda: log_sheet.append_row(row, value_input_option="USER_ENTERED")
            )
            
        except Exception as e:
            print(f"⚠️ Warning: Could not log to general sheet: {e}")

# Singleton instance
_instance: Optional["SubscriptionManager"] = None


def get_subscription_manager() -> "SubscriptionManager":
    """Get or create the singleton SubscriptionManager instance."""
    global _instance
    if _instance is None:
        _instance = SubscriptionManager()
    return _instance


def initialize_subscription_manager() -> "SubscriptionManager":
    """Backward-compatible alias for get_subscription_manager()."""
    return get_subscription_manager()


def check_subscription():
    """
    Main function to check subscription before allowing access
    Returns True if user is authorized, False otherwise
    """
    manager = get_subscription_manager()
    return manager.authenticate_user()


def check_runs_available():
    """
    Check if the current user has runs available before label generation
    Returns True if runs are available, False otherwise
    """
    manager = _instance
    if manager and manager.current_user_id:
        return manager.check_runs_before_generation()
    else:
        print("❌ No active subscription session")
        return False


def log_run_usage(ftid_info, method):
    """
    Function to be called after each successful label generation
    This deducts a run and logs detailed information
    """
    manager = _instance
    if manager and manager.current_user_id:
        return manager.deduct_run_and_log(ftid_info, method)
    else:
        print("❌ Warning: No active subscription session")
        return False


def get_current_user():
    """Get the current authenticated user ID"""
    manager = _instance
    if manager:
        return manager.current_user_id
    return None


def get_remaining_runs():
    """Get the current user's remaining runs"""
    manager = _instance
    if manager and manager.current_user_id:
        return manager.get_current_remaining_runs()
    return 0

# Test function for debugging
def test_subscription_system():
    """
    Test function to verify the subscription system is working
    """
    print("🧪 Testing subscription system...")
    try:
        subscription_manager = SubscriptionManager()
        print("✅ Google Sheets connection successful")
        
        # Test reading the sheet structure
        headers = subscription_manager.sheet.row_values(1)
        print(f"📋 Sheet headers: {headers}")
        
        record_count = len(subscription_manager.sheet.get_all_records())
        print(f"📊 Total user records: {record_count}")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    # Run test if this file is executed directly
    test_subscription_system()
