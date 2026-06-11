import random
import re
from ftid_gen.data_storage import storage


class BackStep(Exception):
    pass

def modify_tracking_number(original_tracking):
    if len(original_tracking) == 18 and original_tracking[:2] == "1Z":
        random_number = ''.join(random.choices("0123456789", k=8))
        return original_tracking[:-8] + random_number
    return original_tracking

def modify_usps_tracking_number(original_tracking):
    if len(original_tracking) == 22 and original_tracking.isdigit():
        random_middle = ''.join(random.choices("0123456789", k=16))
        return original_tracking[:4] + random_middle + original_tracking[-2:]
    return original_tracking

def format_ups_tracking(trk):
    return f"{trk[:2]} {trk[2:5]} {trk[5:8]} {trk[8:10]} {trk[10:14]} {trk[14:]}"

def format_usps_tracking(tracking):
    if len(tracking) == 22:
        return f"{tracking[:4]} {tracking[4:8]} {tracking[8:12]} {tracking[12:16]} {tracking[16:20]} {tracking[20:]}"
    return tracking

def get_valid_ups_tracking():
    previous_tracking = storage.get_previous_ups_tracking()
    
    while True:
        if previous_tracking:
            print(f"Previous UPS tracking: {previous_tracking}")
            tracking_input = input("\nEnter the TRACKING NUMBER (Enter=use previous, or 'b' to go back): ").strip().upper().replace(" ", "")
        else:
            tracking_input = input("\nEnter the TRACKING NUMBER (or 'b' to go back): ").strip().upper().replace(" ", "")
        
        if tracking_input.lower() == 'b':
            raise BackStep()
        elif tracking_input == '' and previous_tracking or (tracking_input.lower() == 'p' and previous_tracking):
            storage.save_ups_tracking(previous_tracking)
            return previous_tracking
        elif len(tracking_input) == 18 and tracking_input.startswith("1Z") and re.match("^[A-Z0-9]+$", tracking_input):
            storage.save_ups_tracking(tracking_input)
            return tracking_input
        print("Invalid UPS tracking number. Must be 18 characters starting with '1Z'.")

def get_valid_usps_tracking():
    previous_tracking = storage.get_previous_usps_tracking()
    
    while True:
        if previous_tracking:
            print(f"Previous USPS tracking: {previous_tracking}")
            tracking_input = input("\nEnter the USPS TRACKING NUMBER (Enter=use previous, or 'b' to go back): ").strip().replace(" ", "")
        else:
            tracking_input = input("\nEnter the USPS TRACKING NUMBER (or 'b' to go back): ").strip().replace(" ", "")
        
        if tracking_input.lower() == 'b':
            raise BackStep()
        elif (tracking_input == '' and previous_tracking) or (tracking_input.lower() == 'p' and previous_tracking):
            storage.save_usps_tracking(previous_tracking)
            return previous_tracking
        elif (len(tracking_input) == 22 or len(tracking_input) == 30) and tracking_input.isdigit():
            storage.save_usps_tracking(tracking_input)
            return tracking_input
        print("Invalid USPS tracking number. Must be 22 digits.")

def get_valid_fedex_tracking():
    previous_tracking = storage.get_previous_fedex_tracking()
    
    while True:
        if previous_tracking:
            print(f"Previous FedEx tracking: {previous_tracking}")
            tracking_input = input("\nEnter the FEDEX TRACKING NUMBER (Enter=use previous, or 'b' to go back): ").strip().replace(" ", "")
        else:
            tracking_input = input("\nEnter the FEDEX TRACKING NUMBER (or 'b' to go back): ").strip().replace(" ", "")
        
        if tracking_input.lower() == 'b':
            raise BackStep()
        elif (tracking_input == '' and previous_tracking) or (tracking_input.lower() == 'p' and previous_tracking):
            storage.save_fedex_tracking(previous_tracking)
            return previous_tracking
        elif len(tracking_input) >= 12 and tracking_input.isdigit():
            storage.save_fedex_tracking(tracking_input)
            return tracking_input
        print("Invalid FedEx tracking number. Must be at least 12 digits.")

def modify_fedex_tracking_number(original_tracking):
    if len(original_tracking) >= 12 and original_tracking.isdigit():
        # Keep first 4 digits, randomize middle section, keep last 2
        if len(original_tracking) >= 6:
            random_middle_length = len(original_tracking) - 6
            random_middle = ''.join(random.choices("0123456789", k=random_middle_length))
            return original_tracking[:4] + random_middle + original_tracking[-2:]
    return original_tracking

def format_fedex_tracking(tracking):
    # FedEx tracking can vary in length, basic formatting
    if len(tracking) >= 12:
        return f"{tracking[:4]} {tracking[4:8]} {tracking[8:12]} {tracking[12:]}"
    return tracking
