#!/usr/bin/env python3

import sys
import os

# Define the base path - set to current directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import subscription manager
from user_tracking.subscription_manager import check_subscription, log_run_usage, check_runs_available

from ftid_gen.config import TEMPLATES, FEDEX_TRACKING_PREFIX
from ftid_gen.ftid_generator import (
    generate_ftid_addresses,
    generate_usps_ftid_addresses,
    generate_fedex_ftid_addresses,
    regenerate_from_zips
)
from ftid_gen.label_processor import process_label
from user_tracking.csv_manager import save_run_to_csv, load_history
from ftid_gen.settings_manager import settings
from ftid_gen.settings_menu import settings_menu
from ftid_gen.previous_maxicode import previous_maxicode
from ftid_gen.excel_importer import excel_importer
from ftid_gen.address_utils import auto_fill_from_zip
from ftid_gen.enhanced_maxicode import enhanced_maxicode
from datetime import datetime
import img2pdf
from PIL import Image

# Action signals returned by menu handlers
ACTION_MAIN_MENU = "main_menu"
ACTION_RERUN = "rerun"
ACTION_QUIT = "quit"


def create_labels_pdf(image_paths):
    """Create a PDF with all labels using img2pdf (most reliable method)"""
    try:
        valid_paths = [p for p in image_paths if p and os.path.exists(p)]

        if not valid_paths:
            print("❌ No valid label images found for PDF creation.")
            return None

        print(f"\n📸 Creating PDF from {len(valid_paths)} labels...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        downloads_folder = os.path.expanduser("~/Downloads")
        pdf_path = os.path.join(downloads_folder, f"batch_labels_{timestamp}.pdf")

        try:
            print("💾 Using img2pdf for clean conversion...")
            with open(pdf_path, "wb") as f:
                img2pdf.convert(valid_paths, outputstream=f)

            print(f"✅ PDF created: {pdf_path}")
            return pdf_path

        except Exception:

            rgb_images = []
            for path in valid_paths:
                img = Image.open(path)
                if img.mode == 'RGBA':
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3])
                    rgb_images.append(rgb_img)
                elif img.mode != 'RGB':
                    rgb_images.append(img.convert('RGB'))
                else:
                    rgb_images.append(img.copy())
                img.close()

            if len(rgb_images) == 1:
                rgb_images[0].save(pdf_path, "PDF", resolution=100.0)
            else:
                rgb_images[0].save(pdf_path, "PDF", save_all=True, append_images=rgb_images[1:], resolution=100.0)

            for img in rgb_images:
                img.close()

            print(f"✅ PDF created: {pdf_path}")
            return pdf_path

    except Exception as e:
        print(f"❌ Error creating PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


def _select_template_and_data(ftid_info, method):
    """Return (name, data, template_path) for a given method and ftid_info."""
    template_keys = {
        "FTID_UPS": "4",
        "FTID_USPS": "5",
        "FTID_FEDEX": "6",
    }
    template_key = template_keys.get(method)
    if not template_key:
        raise ValueError(f"Unsupported FTID method: {method}")

    name, _, template = TEMPLATES[template_key]
    data = ftid_info["tracking_bar"]
    return name, data, template


def handle_input(choice):
    """Handle numeric template choices. Returns ftid_info if label was generated, else None."""
    if choice.lower() == "t":
        print('Not an available option.')
        return None

    if choice in TEMPLATES:
        name, data, template = TEMPLATES[choice]

        if choice == "4":
            if not check_runs_available():
                return None
            ftid_info = generate_ftid_addresses()
            if not ftid_info:
                return None
            data = ftid_info["tracking_bar"]
            _, _ = process_label(name, data, os.path.join(SCRIPT_DIR, template), SCRIPT_DIR, ftid_info)
            save_run_to_csv(ftid_info, "FTID_UPS")
            log_run_usage(ftid_info, "FTID_UPS")
            return ftid_info

        elif choice == "5":
            if not check_runs_available():
                return None
            ftid_info = generate_usps_ftid_addresses()
            if not ftid_info:
                return None
            data = ftid_info["tracking_bar"]
            _, _ = process_label(name, data, os.path.join(SCRIPT_DIR, template), SCRIPT_DIR, ftid_info)
            save_run_to_csv(ftid_info, "FTID_USPS")
            log_run_usage(ftid_info, "FTID_USPS")
            return ftid_info

        elif choice == "6":
            if not check_runs_available():
                return None
            ftid_info = generate_fedex_ftid_addresses()
            if not ftid_info:
                return None
            data = ftid_info["tracking_bar"]
            _, _ = process_label(name, data, os.path.join(SCRIPT_DIR, template), SCRIPT_DIR, ftid_info)
            save_run_to_csv(ftid_info, "FTID_FEDEX")
            log_run_usage(ftid_info, "FTID_FEDEX")
            return ftid_info

        else:
            print('Not an available option.')
    else:
        print('Not an available option.')
        print(f"Invalid choice: {choice}")
    return None


def view_history():
    """View and rerun previous FTID runs with new addresses. Returns an action signal."""
    history = load_history()
    if not history:
        print("\nNo history found.")
        return ACTION_MAIN_MENU

    print("\n=== Previous Runs ===")
    for idx, row in enumerate(history):
        sender_zip = row['sender_city_state_zip'].split()[-1]
        receiver_zip = row['receiver_city_state_zip'].split()[-1]
        print(f"{idx+1}: {row['method']} | Sender ZIP: {sender_zip} | Receiver ZIP: {receiver_zip} | Tracking: {row['tracking_number']}")

    try:
        selection = input("\nEnter a number to rerun automatically, or press Enter to select first entry: ").strip()

        if not selection:
            selection = "1"

        selected = int(selection)
        if 1 <= selected <= len(history):
            if not check_runs_available():
                return ACTION_MAIN_MENU

            row = history[selected - 1]
            sender_zip = row['sender_city_state_zip'].split()[-1]
            receiver_zip = row['receiver_city_state_zip'].split()[-1]
            method = row["method"]

            print(f"\n📋 Selected run: {method}")
            print(f"Sender ZIP: {sender_zip}")
            print(f"Receiver ZIP: {receiver_zip}")
            print(f"Modified Tracking: {row['tracking_number']}")

            original_tracking = row.get('original_tracking') or row['tracking_number']
            print(f"Using saved tracking: {original_tracking}")

            print(f"\nGenerating NEW addresses using saved ZIP codes...")
            ftid_info = regenerate_from_zips(sender_zip, receiver_zip, original_tracking, method)

            if ftid_info:
                print(f"\n=== Re-Generated {method} Info ===")
                print(f"Sender: {ftid_info['sender']}")
                print(f"Sender Address: -{ftid_info['sender_address']}-")
                print(f"Sender City/State/Zip: -{ftid_info['sender_2nd_line']}-")
                print(f"Receiver: {ftid_info['receiver']}")
                print(f"Receiver Address: -{ftid_info['receiver_address']}-")
                print(f"Receiver City/State/Zip: {ftid_info['receiver_2nd_line']}")
                print(f"New Modified Tracking: {ftid_info['tracking_number']}")

                name, data, template = _select_template_and_data(ftid_info, method)

                save_run_to_csv(ftid_info, method)
                _, _ = process_label(name, data, os.path.join(SCRIPT_DIR, template), SCRIPT_DIR, ftid_info)
                log_run_usage(ftid_info, method)

                return ACTION_RERUN
            else:
                print("❌ Failed to regenerate addresses.")
        else:
            print("\nInvalid selection.")
    except ValueError:
        print("\nInvalid input. Please enter a number.")
    return ACTION_MAIN_MENU


def post_run_menu():
    """Menu shown after processing a label. Returns an action signal."""
    print("\n=== What next? ===")
    print("1: Main menu")
    print("2: Rerun previous FTID")
    print("3: Quit")
    opt = input("Enter choice: ").strip()

    if not opt:
        opt = "2"

    if opt == "1":
        return ACTION_MAIN_MENU
    elif opt == "2":
        return ACTION_RERUN
    elif opt == "3":
        return ACTION_QUIT
    else:
        print("Invalid choice, returning to main menu.")
        return ACTION_MAIN_MENU


def rerun_previous_ftid(last_ftid_info):
    """Rerun the last FTID with new addresses but same ZIP codes. Returns an action signal."""
    if not check_runs_available():
        return ACTION_MAIN_MENU

    last_method = None
    original_tracking = None
    sender_zip = None
    receiver_zip = None

    if last_ftid_info:
        if last_ftid_info['tracking_number'].startswith("1Z"):
            last_method = "FTID_UPS"
        elif len(last_ftid_info['tracking_number']) >= 12 and last_ftid_info['tracking_number'].isdigit():
            if len(last_ftid_info['tracking_number']) == 22:
                last_method = "FTID_USPS"
            else:
                last_method = "FTID_FEDEX"
        else:
            last_method = "FTID_USPS"

        original_tracking = last_ftid_info.get('tracking_bar', last_ftid_info['tracking_number'])
        sender_zip = last_ftid_info['sender_2nd_line'].split()[-1]
        receiver_zip = last_ftid_info['receiver_2nd_line'].split()[-1]

    else:
        history = load_history()
        if history:
            last_row = history[-1]
            last_method = last_row["method"]
            sender_zip = last_row["sender_city_state_zip"].split()[-1]
            receiver_zip = last_row["receiver_city_state_zip"].split()[-1]
            print(f"\n📋 Last run was {last_method}")
            print(f"Sender ZIP: {sender_zip}, Receiver ZIP: {receiver_zip}")
            if last_method == "FTID_UPS":
                original_tracking_input = input("Enter the original UPS tracking number (18 chars, starts with 1Z) or press Enter for previous: ").strip().upper().replace(" ", "")
                if not original_tracking_input:
                    original_tracking = last_row.get('original_tracking') or last_row['tracking_number']
                else:
                    original_tracking = original_tracking_input
            elif last_method == "FTID_FEDEX":
                original_tracking_input = input("Enter the original FedEx tracking number (12+ digits) or press Enter for previous: ").strip().replace(" ", "")
                if not original_tracking_input:
                    original_tracking = last_row.get('original_tracking') or last_row['tracking_number']
                else:
                    original_tracking = original_tracking_input
            else:
                original_tracking_input = input("Enter the original USPS tracking number (22 digits) or press Enter for previous: ").strip().replace(" ", "")
                if not original_tracking_input:
                    original_tracking = last_row.get('original_tracking') or last_row['tracking_number']
                else:
                    original_tracking = original_tracking_input

    if last_method and sender_zip and receiver_zip and original_tracking:
        print(f"\n🔄 Re-running {last_method} with NEW random addresses...")

        ftid_info = regenerate_from_zips(sender_zip, receiver_zip, original_tracking, last_method)

        if ftid_info:
            print(f"\n=== Re-Generated {last_method} Info ===")
            print(f"Sender: {ftid_info['sender']}")
            print(f"Sender Address: -{ftid_info['sender_address']}-")
            print(f"Sender City/State/Zip: {ftid_info['sender_2nd_line']}")
            print(f"Receiver: {ftid_info['receiver']}")
            print(f"Receiver Address: -{ftid_info['receiver_address']}-")
            print(f"Receiver City/State/Zip: {ftid_info['receiver_2nd_line']}")
            print(f"New Modified Tracking: {ftid_info['tracking_number']}")

            name, data, template = _select_template_and_data(ftid_info, last_method)

            save_run_to_csv(ftid_info, last_method)
            _, _ = process_label(name, data, os.path.join(SCRIPT_DIR, template), SCRIPT_DIR, ftid_info)
            log_run_usage(ftid_info, last_method)

            return post_run_menu()
        else:
            print("❌ Failed to regenerate addresses.")
    else:
        print("\n❌ No previous FTID run found or missing information.")
    return ACTION_MAIN_MENU


def show_help():
    """Display help information for all menu options"""
    from ftid_gen.config import VERSION
    print("\n" + "="*60)
    print("📖 FTID LABEL GENERATOR - HELP")
    print("="*60)
    print(f"\nVersion: {VERSION}")
    print("\n--- Label Generation ---")
    print("  4: Generate UPS FTID label with random addresses")
    print("  5: Generate USPS FTID label with random addresses")
    print("  6: Generate FedEx FTID label with random addresses")
    print("\n--- Data Management ---")
    print("  7: View history of previous label runs")
    print("  8: Import addresses from Excel/CSV for batch processing")
    print("  9: Reuse previous MaxiCode entries")
    print("\n--- Advanced Features ---")
    print("  m: Enhanced MaxiCode generator (no character limits)")
    print("  s: Application settings (defaults, preferences)")
    print("\n--- Keyboard Shortcuts ---")
    print("  Enter: Use previous value (when available)")
    print("  b: Go back to previous step")
    print("  q: Quit application")
    print("\n" + "="*60)
    input("\nPress Enter to return to main menu...")


def handle_excel_import():
    """Handle Excel/CSV import functionality"""
    print("\n" + "="*60)
    print("📁 EXCEL/CSV IMPORT")
    print("="*60)

    if not check_runs_available():
        return

    results = excel_importer.show_import_menu()

    if results:
        print(f"\n🔄 Processing {len(results)} imported entries...")

        label_paths = []

        for result in results:
            try:
                method = result['method']
                tracking_bar = result['original_tracking']
                if method == "FTID_FEDEX":
                    tracking_bar = f"{FEDEX_TRACKING_PREFIX}{result['original_tracking']}"

                ftid_info = {
                    "sender": result['sender_info']['name'],
                    "sender_address": result['sender_info']['address'],
                    "sender_2nd_line": f"{result['sender_info']['city']} {result['sender_info']['state']} {result['sender_info']['zip_code']}",
                    "receiver": result['receiver_info']['name'],
                    "receiver_address": result['receiver_info']['address'],
                    "receiver_2nd_line": f"{result['receiver_info']['city']} {result['receiver_info']['state']} {result['receiver_info']['zip_code']}",
                    "tracking_number": result['modified_tracking'],
                    "tracking_bar": tracking_bar,
                    "receiver_zip": result['receiver_zip'],
                    "sender_zip": result['sender_zip'],
                    "original_tracking": result['original_tracking']
                }

                name, data, template = _select_template_and_data(ftid_info, method)

                _, label_path = process_label(name, data, os.path.join(SCRIPT_DIR, template), SCRIPT_DIR, ftid_info)
                label_paths.append(label_path)

                save_run_to_csv(ftid_info, method)
                log_run_usage(ftid_info, method)

                previous_maxicode.add_maxicode(
                    data, method, result['original_tracking'],
                    result['sender_info'], result['receiver_info']
                )

                print(f"✅ Processed row {result['row_number']}: {method}")

            except Exception as e:
                print(f"❌ Error processing row {result['row_number']}: {e}")
                continue

        print(f"\n🎉 Batch processing completed! Processed {len(results)} labels.")

        if label_paths:
            pdf_path = create_labels_pdf(label_paths)
            if pdf_path:
                print(f"\n📄 PDF saved to Downloads folder")


def handle_previous_maxicode():
    """Handle previous Maxicode selection"""
    print("\n" + "="*60)
    print("📋 PREVIOUS MAXICODE ENTRIES")
    print("="*60)

    if not check_runs_available():
        return

    entry = previous_maxicode.show_recent_entries_menu()

    if entry:
        print(f"\n🔄 Reusing Maxicode entry: {entry['preview']}")

        sender_zip = entry['sender_info']['zip_code']
        receiver_zip = entry['receiver_info']['zip_code']
        original_tracking = entry['tracking_number']
        method = entry['method']

        print(f"Regenerating addresses for {method}...")
        ftid_info = regenerate_from_zips(sender_zip, receiver_zip, original_tracking, method)

        if ftid_info:
            name, data, template = _select_template_and_data(ftid_info, method)

            _, _ = process_label(name, data, os.path.join(SCRIPT_DIR, template), SCRIPT_DIR, ftid_info)
            save_run_to_csv(ftid_info, method)
            log_run_usage(ftid_info, method)

            print("✅ Label generated successfully!")
        else:
            print("❌ Failed to regenerate addresses.")


def handle_enhanced_maxicode():
    """Handle Enhanced Maxicode generation with no limits"""
    print("\n" + "="*60)
    print("🚀 ENHANCED MAXICODE GENERATOR")
    print("="*60)
    print("Features:")
    print("• No character limits")
    print("• Auto-populated from your previous inputs")
    print("• Auto-calculated city/state from ZIP codes")
    print("• Zero manual input required!")
    print("="*60)

    print("\n1. Generate Maxicode automatically (using your previous data)")
    print("2. Modify existing Maxicode data")
    print("0. Back to main menu")

    choice = input("\nEnter your choice: ").strip()

    if not choice:
        choice = "1"

    if choice == "1":
        print("\n🔄 Generating Maxicode using your previous inputs...")
        maxicode_data = enhanced_maxicode.create_maxicode_from_scratch()
        if maxicode_data:
            print(f"\n✅ Enhanced Maxicode generated successfully!")
            print(f"📏 Length: {len(maxicode_data)} characters (NO LIMITS)")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"enhanced_maxicode_{timestamp}.txt"

            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(maxicode_data)
                print(f"💾 Auto-saved to {filename}")
            except Exception as e:
                print(f"❌ Error saving file: {e}")

    elif choice == "2":
        print("\nEnter existing Maxicode data:")
        existing_data = input("Maxicode data: ").strip()

        if existing_data:
            modified_data = enhanced_maxicode.modify_existing_maxicode(existing_data)
            if modified_data:
                print(f"\n✅ Enhanced Maxicode modified successfully!")
                print(f"📏 New length: {len(modified_data)} characters (NO LIMITS)")

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"modified_maxicode_{timestamp}.txt"

                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(modified_data)
                    print(f"💾 Auto-saved to {filename}")
                except Exception as e:
                    print(f"❌ Error saving file: {e}")
        else:
            print("❌ No data provided.")

    elif choice == "0":
        return
    else:
        print("❌ Invalid choice.")


def startup():
    """Startup function that handles subscription check before main application"""
    print("🚀 Starting FTID Label Generator...")
    print("📋 Version 2.0 - Enhanced with Settings & Automation")

    if not check_subscription():
        print("\n❌ Access denied. Exiting...")
        sys.exit(1)

    print("\n" + "="*50)
    print("🎉 ACCESS GRANTED - Welcome to FTID Generator!")
    print("="*50)

    from_address = settings.get_from_address()
    if from_address.get('zip_code'):
        print(f"📍 Default From: {from_address.get('city', 'N/A')}, {from_address.get('state', 'N/A')} {from_address.get('zip_code', 'N/A')}")

    auto_generate = settings.get('maxicode.auto_generate', True)
    no_limit = settings.get('maxicode.no_character_limit', True)
    print(f"🔢 Maxicode: {'Auto-generate' if auto_generate else 'Manual mode'} | {'No limits' if no_limit else 'Limited'}")

    main()


def main():
    """Main menu loop - uses while loop instead of recursion to avoid stack overflow."""
    from ftid_gen.config import VERSION
    from ftid_gen.console_utils import print_header, print_menu

    last_ftid_info = None

    while True:
        print_header(f"🏷️  FTID LABEL GENERATOR v{VERSION}", "Generate shipping labels with ease")

        menu_options = [
            ("4", "FTID UPS - Random addresses, modified tracking"),
            ("5", "FTID USPS - Random addresses, modified tracking"),
            ("6", "FTID FEDEX - Random addresses, modified tracking"),
            ("7", "View previous runs"),
            ("8", "Import from Excel/CSV"),
            ("9", "Previous Maxicode entries"),
            ("m", "Enhanced Maxicode Generator (No Limits)"),
            ("s", "Settings"),
            ("h", "Help"),
            ("q", "Quit"),
        ]

        print_menu(menu_options, "Select an Option")

        choice = input("\nEnter your selection: ").strip()

        if not choice:
            choice = "9"

        action = ACTION_MAIN_MENU

        if choice == "7":
            action = view_history()
        elif choice == "8":
            handle_excel_import()
        elif choice == "9":
            handle_previous_maxicode()
        elif choice.lower() == "m":
            handle_enhanced_maxicode()
        elif choice.lower() == "s":
            settings_menu.show_main_menu()
        elif choice.lower() == "h":
            show_help()
        elif choice.lower() == "q":
            print("Goodbye!")
            sys.exit(0)
        else:
            ftid_info = handle_input(choice)
            if ftid_info is not None:
                last_ftid_info = ftid_info
                action = post_run_menu()

        if action == ACTION_QUIT:
            print("Goodbye!")
            sys.exit(0)
        elif action == ACTION_RERUN:
            action = rerun_previous_ftid(last_ftid_info)
            if action == ACTION_QUIT:
                print("Goodbye!")
                sys.exit(0)


if __name__ == "__main__":
    startup()
