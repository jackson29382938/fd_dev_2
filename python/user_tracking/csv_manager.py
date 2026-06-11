import os
import csv
import datetime
from ftid_gen.config import CSV_LOG_PATH

def save_run_to_csv(info, method):
    """
    Save run information to local CSV file for backup/local history
    """
    if info is None:
        return

    row = {
        "timestamp": datetime.datetime.now().isoformat(),
        "method": method,
        "sender_name": info["sender"],
        "sender_address": info["sender_address"],
        "sender_city_state_zip": info["sender_2nd_line"],
        "receiver_name": info["receiver"],
        "receiver_address": info["receiver_address"],
        "receiver_city_state_zip": info["receiver_2nd_line"],
        "tracking_number": info["tracking_number"],
        "original_tracking": info.get("original_tracking", info.get("tracking_bar", info["tracking_number"])),
        "sender_zip": info.get("sender_zip", info["sender_2nd_line"].split()[-1] if info.get("sender_2nd_line") else "N/A"),
        "receiver_zip": info.get("receiver_zip", info["receiver_2nd_line"].split()[-1] if info.get("receiver_2nd_line") else "N/A")
    }

    file_exists = os.path.exists(CSV_LOG_PATH)
    with open(CSV_LOG_PATH, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def load_history():
    """
    Load history from local CSV file for offline viewing
    Note: This is now supplementary to the Google Sheets user-specific tracking
    """
    if not os.path.exists(CSV_LOG_PATH):
        return []
    
    with open(CSV_LOG_PATH, newline='') as file:
        return list(csv.DictReader(file))

def save_user_run_to_csv(info, method, user_id):
    """
    Enhanced function to save run with user information
    This works alongside the Google Sheets logging
    """
    if info is None:
        return

    # Create user-specific CSV path
    user_csv_path = CSV_LOG_PATH.replace('.csv', f'_user_{user_id}.csv')
    
    row = {
        "timestamp": datetime.datetime.now().isoformat(),
        "user_id": user_id,
        "method": method,
        "sender_name": info["sender"],
        "sender_address": info["sender_address"],
        "sender_city_state_zip": info["sender_2nd_line"],
        "receiver_name": info["receiver"],
        "receiver_address": info["receiver_address"],
        "receiver_city_state_zip": info["receiver_2nd_line"],
        "tracking_number": info["tracking_number"],
        "original_tracking": info.get("original_tracking", info.get("tracking_bar", info["tracking_number"])),
        "sender_zip": info.get("sender_zip", info["sender_2nd_line"].split()[-1] if info.get("sender_2nd_line") else "N/A"),
        "receiver_zip": info.get("receiver_zip", info["receiver_2nd_line"].split()[-1] if info.get("receiver_2nd_line") else "N/A")
    }

    file_exists = os.path.exists(user_csv_path)
    with open(user_csv_path, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def load_user_history(user_id):
    """
    Load history for a specific user from their CSV file
    """
    user_csv_path = CSV_LOG_PATH.replace('.csv', f'_user_{user_id}.csv')
    
    if not os.path.exists(user_csv_path):
        return []
    
    with open(user_csv_path, newline='') as file:
        return list(csv.DictReader(file))