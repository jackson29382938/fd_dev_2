from ftid_gen.address_utils import get_valid_zipcode, get_address, generate_full_name, auto_fill_from_zip
from ftid_gen.tracking_utils import (
    get_valid_ups_tracking,
    get_valid_usps_tracking,
    modify_tracking_number,
    modify_usps_tracking_number,
    get_valid_fedex_tracking,
    modify_fedex_tracking_number,
    BackStep,
)
from ftid_gen.config import FEDEX_TRACKING_PREFIX
from user_tracking.google_drive_logger import log_to_google_drive
from user_tracking.subscription_manager import log_run_usage
from ftid_gen.settings_manager import settings
from ftid_gen.previous_maxicode import previous_maxicode
from typing import Optional, Dict, Any


def generate_ftid_addresses():
    return _generate_carrier_ftid_addresses(
        carrier="UPS",
        method="FTID_UPS",
        modify_func=modify_tracking_number,
        get_tracking_func=get_valid_ups_tracking,
    )


def generate_usps_ftid_addresses():
    return _generate_carrier_ftid_addresses(
        carrier="USPS",
        method="FTID_USPS",
        modify_func=modify_usps_tracking_number,
        get_tracking_func=get_valid_usps_tracking,
    )


def generate_fedex_ftid_addresses():
    return _generate_carrier_ftid_addresses(
        carrier="FEDEX",
        method="FTID_FEDEX",
        modify_func=modify_fedex_tracking_number,
        get_tracking_func=get_valid_fedex_tracking,
    )


def _generate_carrier_ftid_addresses(carrier, method, modify_func, get_tracking_func):
    """Shared implementation for UPS/USPS/FedEx FTID address generation."""
    print(f"=== {carrier} FTID Address Generation ===")

    if settings.get('previous_maxicode.enabled', True):
        print("\n1. Use previous Maxicode entry")
        print("2. Create new entry")
        choice = input("Press Enter to create new, or type 1 to use previous: ").strip()
        if choice == "":
            choice = "2"

        if choice == "1":
            entry = previous_maxicode.show_recent_entries_menu()
            if entry:
                return _reuse_previous_entry(entry, method)

    sender_zip = _get_sender_zip()
    if not sender_zip:
        return None

    receiver_zip = _get_receiver_zip()
    if not receiver_zip:
        return None

    tracking_input = get_tracking_func()
    if not tracking_input:
        return None

    sender_info = _generate_address(sender_zip, "Sender")
    if not sender_info:
        return None

    receiver_info = _generate_address(receiver_zip, "Receiver")
    if not receiver_info:
        return None

    modified_tracking = modify_func(tracking_input)

    tracking_bar = tracking_input
    if method == "FTID_FEDEX":
        tracking_bar = f"{FEDEX_TRACKING_PREFIX}{tracking_input}"

    ftid_info = create_ftid_info(
        sender_info['name'],
        sender_info,
        receiver_info['name'],
        receiver_info,
        modified_tracking,
        tracking_input,
        tracking_bar=tracking_bar,
    )

    if ftid_info:
        previous_maxicode.add_maxicode(
            ftid_info['tracking_bar'], method, tracking_input,
            sender_info, receiver_info
        )

    return ftid_info


def create_ftid_info(
    sender_name,
    sender_info,
    receiver_name,
    receiver_info,
    modified_tracking,
    original_tracking,
    tracking_bar=None,
):
    info = {
        "sender": sender_name,
        "sender_address": sender_info['address'],
        "sender_2nd_line": f"{sender_info['city']} {sender_info['state']} {sender_info['zip_code']}",
        "receiver": receiver_name,
        "receiver_address": receiver_info['address'],
        "receiver_2nd_line": f"{receiver_info['city']} {receiver_info['state']} {receiver_info['zip_code']}",
        "tracking_number": modified_tracking,
        "tracking_bar": tracking_bar or original_tracking,
        "receiver_zip": receiver_info['zip_code'],
        "sender_zip": sender_info['zip_code'],
        "original_tracking": original_tracking
    }

    print(f"\n=== Generated FTID Info ===")
    for key, value in info.items():
        if key not in ['tracking_bar', 'receiver_zip', 'sender_zip', 'original_tracking']:
            print(f"{key.replace('_', ' ').title()}: {value}")

    try:
        log_to_google_drive(
            sender_zip=info["sender_2nd_line"].split()[-1],
            receiver_zip=info["receiver_2nd_line"].split()[-1],
            tracking_number=info["tracking_number"]
        )
    except Exception as e:
        print(f"⚠️ Could not log to Google Drive: {e}")

    return info


def regenerate_from_zips(sender_zip, receiver_zip, original_tracking, method, address_choice=None, allow_fallback_prompt=True):
    print("\n--- Regenerating Sender Address ---")
    sender_info = get_address(sender_zip, choice=address_choice, allow_fallback_prompt=allow_fallback_prompt)
    sender_name = generate_full_name()

    print("\n--- Regenerating Receiver Address ---")
    receiver_info = get_address(receiver_zip, choice=address_choice, allow_fallback_prompt=allow_fallback_prompt)
    receiver_name = generate_full_name()

    if not sender_info or not receiver_info:
        print("❌ failed - contact @halal_hamburger")
        return None

    if method == "FTID_UPS":
        new_modified_tracking = modify_tracking_number(original_tracking)
    elif method == "FTID_FEDEX":
        new_modified_tracking = modify_fedex_tracking_number(original_tracking)
    else:
        new_modified_tracking = modify_usps_tracking_number(original_tracking)

    tracking_bar = original_tracking
    if method == "FTID_FEDEX":
        tracking_bar = f"{FEDEX_TRACKING_PREFIX}{original_tracking}"

    return create_ftid_info(
        sender_name,
        sender_info,
        receiver_name,
        receiver_info,
        new_modified_tracking,
        original_tracking,
        tracking_bar=tracking_bar,
    )


def _get_sender_zip():
    """Get sender ZIP code, using default if available"""
    from_address = settings.get_from_address()
    default_zip = from_address.get('zip_code')

    if default_zip:
        print(f"Default From ZIP: {default_zip}")
        use_default = input("Use default From ZIP? (Y/n): ").strip().lower()
        if use_default != 'n':
            return default_zip

    return get_valid_zipcode("Enter Sender Zip Code: ", "sender_zip")


def _get_receiver_zip():
    """Get receiver ZIP code"""
    return get_valid_zipcode("Enter Receiver Zip Code: ", "receiver_zip")


def _generate_address(zip_code, role="sender"):
    """Generate an address for the given role (sender or receiver)."""
    print(f"\n--- {role.title()} Address ---")

    location_info = auto_fill_from_zip(zip_code)
    if location_info:
        print(f"Auto-detected: {location_info['city']}, {location_info['state']} {zip_code}")

    address_info = get_address(zip_code)
    if not address_info:
        return None

    name = generate_full_name()

    return {
        'name': name,
        'address': address_info['address'],
        'city': address_info['city'],
        'state': address_info['state'],
        'zip_code': zip_code
    }


def _reuse_previous_entry(entry, method):
    """Reuse a previous Maxicode entry"""
    sender_zip = entry['sender_info']['zip_code']
    receiver_zip = entry['receiver_info']['zip_code']
    original_tracking = entry['tracking_number']

    print(f"Reusing entry: {entry['preview']}")
    print(f"Regenerating addresses for {method}...")

    return regenerate_from_zips(sender_zip, receiver_zip, original_tracking, method)
