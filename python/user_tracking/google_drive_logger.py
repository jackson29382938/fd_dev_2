import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from pathlib import Path

from user_tracking.credentials import resolve_credentials_path
from user_tracking.ip_utils import get_ip_info

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "requirements", "credentials.json")

SHEET_NAME = "FTID_Log"


def log_to_google_drive(sender_zip, receiver_zip, tracking_number):
    """
    This function now only logs to the general FTID_Log sheet (2nd sheet)
    Individual user logging is handled by the subscription manager
    """
    try:
        ip_info = get_ip_info()

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials_path = resolve_credentials_path(Path(BASE_DIR))
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(credentials_path), scope)
        client = gspread.authorize(creds)

        try:
            sheet = client.open(SHEET_NAME).sheet1
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"⚠️ General FTID_Log sheet not found, skipping general log")
            return

        row = [
            str(datetime.now()),
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
            tracking_number
        ]

        sheet.append_row(row, value_input_option="USER_ENTERED")
    except gspread.exceptions.APIError as gerr:
        print(f"❌ Google Sheets API error: {gerr.response.text if hasattr(gerr, 'response') else gerr}")
    except Exception as e:
        print(f"❌ General error logging to Google Sheets: {e}")
