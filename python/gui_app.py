#!/usr/bin/env python3
"""
FTID Label Generator - Desktop GUI Application
A modern, beautiful native desktop application using CustomTkinter.
Fully integrated with backend label generation.
"""
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
import threading
import os
import sys
import csv
from datetime import datetime

# Keep imports scoped to this standalone Python workspace.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ftid_gen.config import VERSION, CSV_LOG_PATH, BASE_DIR, FEDEX_TRACKING_PREFIX
from ftid_gen.settings_manager import settings

# Set appearance mode and default color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# Import subscription manager for authentication
try:
    from user_tracking.subscription_manager import SubscriptionManager, initialize_subscription_manager
    SUBSCRIPTION_AVAILABLE = True
except ImportError:
    SUBSCRIPTION_AVAILABLE = False


class LoginFrame(ctk.CTkFrame):
    """Login frame requiring user authentication"""
    
    def __init__(self, parent, on_login_success):
        super().__init__(parent)
        self.parent = parent
        self.on_login_success = on_login_success
        self.subscription_manager = None
        self.attempts = 0
        self.max_attempts = 3
        
        # Initialize subscription manager
        if SUBSCRIPTION_AVAILABLE:
            try:
                self.subscription_manager = initialize_subscription_manager()
            except Exception as e:
                print(f"Warning: Could not initialize subscription manager: {e}")
        
        self.configure(fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Center container
        center_frame = ctk.CTkFrame(self, corner_radius=20, fg_color=("gray90", "gray17"))
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Title
        ctk.CTkLabel(
            center_frame, 
            text="🔐", 
            font=ctk.CTkFont(size=60)
        ).pack(pady=(40, 10))
        
        ctk.CTkLabel(
            center_frame, 
            text="FTID Label Generator", 
            font=ctk.CTkFont(size=28, weight="bold")
        ).pack(pady=(0, 5))
        
        ctk.CTkLabel(
            center_frame, 
            text="Please login to continue", 
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(pady=(0, 30))
        
        # User ID field
        ctk.CTkLabel(center_frame, text="User ID", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=40)
        self.user_id_entry = ctk.CTkEntry(center_frame, width=280, height=45, placeholder_text="Enter your User ID")
        self.user_id_entry.pack(padx=40, pady=(5, 15))
        
        # Passcode field
        ctk.CTkLabel(center_frame, text="Passcode", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=40)
        self.passcode_entry = ctk.CTkEntry(center_frame, width=280, height=45, placeholder_text="Enter your Passcode", show="•")
        self.passcode_entry.pack(padx=40, pady=(5, 25))
        
        # Status label
        self.status_label = ctk.CTkLabel(center_frame, text="", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(0, 10))
        
        # Login button
        self.login_btn = ctk.CTkButton(
            center_frame, 
            text="Login", 
            width=280, 
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.attempt_login
        )
        self.login_btn.pack(padx=40, pady=(0, 40))
        
        # Bind Enter key
        self.user_id_entry.bind("<Return>", lambda e: self.passcode_entry.focus())
        self.passcode_entry.bind("<Return>", lambda e: self.attempt_login())
        
        # Focus on user ID field
        self.user_id_entry.focus()
    
    def attempt_login(self):
        """Attempt to authenticate the user"""
        user_id = self.user_id_entry.get().strip()
        passcode = self.passcode_entry.get().strip()
        
        if not user_id or not passcode:
            self.status_label.configure(text="❌ Please enter both User ID and Passcode", text_color="red")
            return
        
        self.login_btn.configure(state="disabled", text="Authenticating...")
        self.status_label.configure(text="⏳ Verifying credentials...", text_color="gray")
        self.update()
        
        # Authenticate in a thread to avoid freezing
        threading.Thread(target=self._do_login, args=(user_id, passcode), daemon=True).start()
    
    def _do_login(self, user_id, passcode):
        """Perform login check"""
        try:
            if not self.subscription_manager:
                # No subscription manager - allow access for development
                self.after(0, lambda: self._login_success(user_id, 999999))
                return
            
            # Find user in Google Sheets
            user_data = self.subscription_manager.find_user(user_id, passcode)
            
            if user_data is None:
                self.attempts += 1
                remaining = self.max_attempts - self.attempts
                if remaining > 0:
                    self.after(0, lambda: self._login_failed(f"Invalid credentials. {remaining} attempts remaining."))
                else:
                    self.after(0, self._too_many_attempts)
                return
            
            # Check remaining runs
            remaining_runs = user_data.get('remaining_runs', 0)
            if remaining_runs <= 0:
                self.after(0, lambda: self._login_failed("No runs remaining. Please contact support."))
                return
            
            # Set current user in subscription manager
            self.subscription_manager.current_user_id = user_id
            self.subscription_manager.current_user_row = user_data.get('row_number')
            
            # Ensure user sheet exists
            self.subscription_manager.ensure_user_sheet_exists(user_id)
            
            self.after(0, lambda: self._login_success(user_id, remaining_runs))
            
        except Exception as e:
            self.after(0, lambda: self._login_failed(f"Error: {str(e)[:50]}"))
    
    def _login_success(self, user_id, remaining_runs):
        """Handle successful login"""
        self.status_label.configure(text=f"✅ Welcome, User {user_id}! ({remaining_runs} runs remaining)", text_color="green")
        self.update()
        self.after(1000, lambda: self.on_login_success(user_id, remaining_runs))
    
    def _login_failed(self, message):
        """Handle failed login"""
        self.login_btn.configure(state="normal", text="Login")
        self.status_label.configure(text=f"❌ {message}", text_color="red")
        self.passcode_entry.delete(0, 'end')
    
    def _too_many_attempts(self):
        """Handle too many failed attempts"""
        self.login_btn.configure(state="disabled", text="Locked")
        self.status_label.configure(text="❌ Too many failed attempts. Please restart the app.", text_color="red")


class FTIDApp(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title(f"FTID Label Generator v{VERSION}")
        self.geometry("1300x850")
        self.minsize(1000, 700)
        
        # User info
        self.current_user_id = None
        self.remaining_runs = 0
        
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Show login first
        self.show_login()
    
    def show_login(self):
        """Show login frame"""
        self.login_frame = LoginFrame(self, self.on_login_complete)
        self.login_frame.grid(row=0, column=0, sticky="nsew")
    
    def on_login_complete(self, user_id, remaining_runs):
        """Called after successful login"""
        self.current_user_id = user_id
        self.remaining_runs = remaining_runs
        
        # Remove login frame
        self.login_frame.destroy()
        
        # Reconfigure grid for main app layout
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        
        # Create navigation sidebar
        self.create_sidebar()
        
        # Create main content area
        self.create_main_content()
        
        # Initialize with home view
        self.show_home()
    
    def create_sidebar(self):
        """Create the navigation sidebar"""
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)
        
        # Logo/Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="🏷️ FTID Generator",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 5))
        
        self.version_label = ctk.CTkLabel(
            self.sidebar,
            text=f"Version {VERSION}",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.version_label.grid(row=1, column=0, padx=20, pady=(0, 25))
        
        # Navigation buttons
        nav_buttons = [
            ("🏠  Home", self.show_home, "#2d5a27"),
            ("📦  UPS Label", self.show_ups_form, "#1f538d"),
            ("📬  USPS Label", self.show_usps_form, "#4a5568"),
            ("🚚  FedEx Label", self.show_fedex_form, "#4a1f75"),
            ("📊  Tracker", self.show_tracking, "#0d6efd"),
            ("📋  History", self.show_history, "#374151"),
            ("📁  Import Excel", self.show_import, "#374151"),
            ("🔲  MaxiCode", self.show_maxicode, "#374151"),
            ("⚙️  Settings", self.show_settings, "#374151"),
        ]
        
        self.nav_buttons = []
        for i, (text, command, color) in enumerate(nav_buttons):
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                command=command,
                height=45,
                anchor="w",
                font=ctk.CTkFont(size=14),
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
                corner_radius=8,
            )
            btn.grid(row=i+2, column=0, padx=12, pady=3, sticky="ew")
            self.nav_buttons.append((btn, color))
        
        # Theme toggle at bottom
        self.theme_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.theme_frame.grid(row=11, column=0, padx=20, pady=20, sticky="ew")
        
        self.theme_label = ctk.CTkLabel(
            self.theme_frame,
            text="🎨 Theme",
            font=ctk.CTkFont(size=12)
        )
        self.theme_label.grid(row=0, column=0, pady=(0, 5), sticky="w")
        
        self.theme_menu = ctk.CTkSegmentedButton(
            self.theme_frame,
            values=["Dark", "Light"],
            command=self.change_theme,
            font=ctk.CTkFont(size=11)
        )
        self.theme_menu.set("Dark")
        self.theme_menu.grid(row=1, column=0, sticky="ew")
    
    def create_main_content(self):
        """Create the main content container"""
        self.main_container = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray92", "gray14"))
        self.main_container.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)
        
        self.current_view = None
    
    def clear_main_content(self):
        """Clear the current view"""
        if self.current_view:
            self.current_view.destroy()
    
    def change_theme(self, new_theme):
        """Change the application theme"""
        ctk.set_appearance_mode(new_theme.lower())
    
    def select_nav_button(self, index):
        """Highlight the selected navigation button"""
        for i, (btn, color) in enumerate(self.nav_buttons):
            if i == index:
                btn.configure(fg_color=color)
            else:
                btn.configure(fg_color="transparent")
    
    # ==================== View Methods ====================
    
    def show_home(self):
        self.clear_main_content()
        self.select_nav_button(0)
        self.current_view = HomeView(self.main_container, self)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
    
    def show_ups_form(self):
        self.clear_main_content()
        self.select_nav_button(1)
        self.current_view = LabelFormView(self.main_container, self, "UPS")
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
    
    def show_usps_form(self):
        self.clear_main_content()
        self.select_nav_button(2)
        self.current_view = LabelFormView(self.main_container, self, "USPS")
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
    
    def show_fedex_form(self):
        self.clear_main_content()
        self.select_nav_button(3)
        self.current_view = LabelFormView(self.main_container, self, "FEDEX")
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
    
    def show_tracking(self):
        self.clear_main_content()
        self.select_nav_button(4)
        self.current_view = TrackingDashboardView(self.main_container, self)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
    
    def show_history(self):
        self.clear_main_content()
        self.select_nav_button(5)
        self.current_view = HistoryView(self.main_container, self)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
    
    def show_import(self):
        self.clear_main_content()
        self.select_nav_button(6)
        self.current_view = ImportView(self.main_container, self)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
    
    def show_maxicode(self):
        self.clear_main_content()
        self.select_nav_button(7)
        self.current_view = MaxiCodeView(self.main_container, self)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
    
    def show_settings(self):
        self.clear_main_content()
        self.select_nav_button(8)
        self.current_view = SettingsView(self.main_container, self)
        self.current_view.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)


# ==================== View Classes ====================

class HomeView(ctk.CTkFrame):
    """Home/Dashboard view with quick actions"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure((0, 1, 2), weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Welcome header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        
        self.header = ctk.CTkLabel(
            header_frame,
            text="Welcome to FTID Generator",
            font=ctk.CTkFont(size=32, weight="bold")
        )
        self.header.pack(anchor="w")
        
        self.subheader = ctk.CTkLabel(
            header_frame,
            text="Generate shipping labels with randomized addresses and modified tracking numbers",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.subheader.pack(anchor="w", pady=(5, 0))
        
        # Quick action cards
        cards = [
            ("📦 UPS Label", "Generate UPS FTID label\nwith MaxiCode barcode", app.show_ups_form, "#1f538d"),
            ("📬 USPS Label", "Generate USPS FTID label\nwith modified tracking", app.show_usps_form, "#2d5a27"),
            ("🚚 FedEx Label", "Generate FedEx FTID label\nwith modified tracking", app.show_fedex_form, "#4a1f75"),
        ]
        
        for i, (title, desc, command, color) in enumerate(cards):
            card = self.create_action_card(title, desc, command, color)
            card.grid(row=1, column=i, padx=8, pady=15, sticky="nsew")
        
        # Recent activity section
        self.activity_frame = ctk.CTkFrame(self, corner_radius=12)
        self.activity_frame.grid(row=2, column=0, columnspan=3, pady=(20, 0), sticky="nsew")
        self.activity_frame.grid_columnconfigure(0, weight=1)
        self.activity_frame.grid_rowconfigure(1, weight=1)
        
        activity_header = ctk.CTkLabel(
            self.activity_frame,
            text="📊 Recent Activity",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        activity_header.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")
        
        # Load recent activity
        self.load_recent_activity()
    
    def create_action_card(self, title, description, command, color):
        """Create a styled action card"""
        card = ctk.CTkFrame(self, corner_radius=15)
        card.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=25, pady=(25, 8))
        
        desc_label = ctk.CTkLabel(
            card,
            text=description,
            font=ctk.CTkFont(size=13),
            text_color="gray",
            justify="center"
        )
        desc_label.grid(row=1, column=0, padx=25, pady=(0, 20))
        
        btn = ctk.CTkButton(
            card,
            text="Generate →",
            command=command,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=color,
            hover_color=self.adjust_color(color, -25),
            corner_radius=10
        )
        btn.grid(row=2, column=0, padx=25, pady=(0, 25), sticky="ew")
        
        return card
    
    def adjust_color(self, hex_color, amount):
        """Adjust hex color brightness"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(max(0, min(255, c + amount)) for c in rgb)
        return '#{:02x}{:02x}{:02x}'.format(*rgb)
    
    def load_recent_activity(self):
        """Load recent activity from CSV"""
        scroll = ctk.CTkScrollableFrame(self.activity_frame, fg_color="transparent")
        scroll.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        
        try:
            if os.path.exists(CSV_LOG_PATH):
                with open(CSV_LOG_PATH, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)[-5:]  # Last 5 entries
                    
                    if rows:
                        for i, row in enumerate(reversed(rows)):
                            item = ctk.CTkFrame(scroll, corner_radius=8, height=50)
                            item.grid(row=i, column=0, pady=3, sticky="ew")
                            item.grid_columnconfigure(1, weight=1)
                            
                            method = row.get('method', 'Unknown')
                            tracking = row.get('tracking_number', 'N/A')[:20]
                            timestamp = row.get('timestamp', '')[:16]
                            
                            icon = {"FTID_UPS": "📦", "FTID_USPS": "📬", "FTID_FEDEX": "🚚"}.get(method, "📋")
                            
                            ctk.CTkLabel(item, text=icon, font=ctk.CTkFont(size=20)).grid(row=0, column=0, padx=15, pady=10)
                            ctk.CTkLabel(item, text=f"{method} - {tracking}...", font=ctk.CTkFont(size=13)).grid(row=0, column=1, sticky="w")
                            ctk.CTkLabel(item, text=timestamp, font=ctk.CTkFont(size=11), text_color="gray").grid(row=0, column=2, padx=15)
                    else:
                        self._show_no_activity(scroll)
            else:
                self._show_no_activity(scroll)
        except Exception:
            self._show_no_activity(scroll)
    
    def _show_no_activity(self, parent):
        ctk.CTkLabel(
            parent,
            text="No recent activity. Generate a label to get started!",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        ).grid(row=0, column=0, pady=30)


class LabelFormView(ctk.CTkFrame):
    """Label generation form view - fully integrated with autofill"""
    
    def __init__(self, parent, app, carrier):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.carrier = carrier
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=3)  # Give form scroll more vertical space
        self.grid_rowconfigure(2, weight=0)
        
        # Load previous values for autofill
        self.previous_values = self._load_previous_values()
        
        # Header with icon
        icons = {"UPS": "📦", "USPS": "📬", "FEDEX": "🚚"}
        colors = {"UPS": "#1f538d", "USPS": "#2d5a27", "FEDEX": "#4a1f75"}
        
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        self.header = ctk.CTkLabel(
            header_frame,
            text=f"{icons.get(carrier, '📦')} Generate {carrier} Label",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        self.header.pack(side="left")
        
        # Form scroll container - larger height, trackpad scrolling enabled by default
        self.form_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=500)
        self.form_scroll.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.form_scroll.grid_columnconfigure((0, 1), weight=1)
        
        # Address sections with autofill
        self.sender_frame = self.create_address_section("Sender", 0, 0)
        self.receiver_frame = self.create_address_section("Receiver", 0, 1)
        
        # Tracking section
        tracking_frame = ctk.CTkFrame(self.form_scroll, corner_radius=12)
        tracking_frame.grid(row=1, column=0, columnspan=2, padx=8, pady=15, sticky="ew")
        tracking_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            tracking_frame,
            text="🔢 Tracking Number",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Tracking format hints
        hints = {
            "UPS": "18 characters starting with 1Z",
            "USPS": "22 digits",
            "FEDEX": "12+ digits"
        }
        
        ctk.CTkLabel(
            tracking_frame,
            text=hints.get(carrier, "Enter tracking number"),
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).grid(row=1, column=0, padx=20, pady=(0, 5), sticky="w")
        
        self.tracking_entry = ctk.CTkEntry(
            tracking_frame,
            placeholder_text=f"Enter {carrier} tracking number",
            height=45,
            font=ctk.CTkFont(size=14)
        )
        self.tracking_entry.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        # Autofill tracking from previous values
        prev_tracking = self.previous_values.get(f'{carrier.lower()}_tracking', '')
        if prev_tracking:
            self.tracking_entry.insert(0, prev_tracking)
        
        # Options section
        options_frame = ctk.CTkFrame(self.form_scroll, corner_radius=12)
        options_frame.grid(row=2, column=0, columnspan=2, padx=8, pady=10, sticky="ew")
        
        ctk.CTkLabel(
            options_frame,
            text="⚙️ Options",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 15), sticky="w")
        
        self.address_type_var = ctk.StringVar(value="fake")
        
        ctk.CTkLabel(options_frame, text="Address Type:", font=ctk.CTkFont(size=13)).grid(row=1, column=0, padx=20, pady=15)
        ctk.CTkRadioButton(options_frame, text="Fake (Generated)", variable=self.address_type_var, value="fake", font=ctk.CTkFont(size=13)).grid(row=1, column=1, padx=15)
        ctk.CTkRadioButton(options_frame, text="Real (Yelp API)", variable=self.address_type_var, value="real", font=ctk.CTkFont(size=13)).grid(row=1, column=2, padx=15, pady=(0, 15))
        
        # Bottom action area
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=3, column=0, sticky="ew", pady=(20, 0))
        action_frame.grid_columnconfigure(0, weight=1)
        
        self.generate_btn = ctk.CTkButton(
            action_frame,
            text="🚀 Generate Label",
            height=55,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color=colors.get(carrier, "#1f538d"),
            hover_color=self.adjust_color(colors.get(carrier, "#1f538d"), -25),
            corner_radius=12,
            command=self.generate_label
        )
        self.generate_btn.grid(row=0, column=0, sticky="ew")
        
        self.progress = ctk.CTkProgressBar(action_frame, height=6)
        self.progress.set(0)
        
        self.status_label = ctk.CTkLabel(
            action_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=2, column=0, pady=(10, 0))
    
    def _load_previous_values(self):
        """Load previous values from data storage for autofill"""
        try:
            from ftid_gen.data_storage import storage
            return {
                'sender_zip': storage.get_previous_sender_zip() or '',
                'receiver_zip': storage.get_previous_receiver_zip() or '',
                'ups_tracking': storage.get_previous_ups_tracking() or '',
                'usps_tracking': storage.get_previous_usps_tracking() or '',
                'fedex_tracking': storage.get_previous_fedex_tracking() or '',
            }
        except Exception as e:
            print(f"⚠️ Could not load previous values: {e}")
            return {}
    
    def create_address_section(self, title, row, column):
        """Create an address input section with autofill"""
        frame = ctk.CTkFrame(self.form_scroll, corner_radius=12)
        frame.grid(row=row, column=column, padx=8, pady=10, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        
        icon = "📤" if title == "Sender" else "📥"
        ctk.CTkLabel(
            frame,
            text=f"{icon} {title} Address",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 15), sticky="w")
        
        # ZIP code with autofill
        ctk.CTkLabel(frame, text="ZIP Code *", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=20, pady=(5, 0), sticky="w")
        zip_entry = ctk.CTkEntry(frame, placeholder_text="5-digit ZIP", height=40, font=ctk.CTkFont(size=13))
        zip_entry.grid(row=2, column=0, padx=20, pady=(3, 15), sticky="ew")
        
        # Autofill from previous values
        prev_zip = self.previous_values.get(f'{title.lower()}_zip', '')
        if prev_zip:
            zip_entry.insert(0, prev_zip)
        
        setattr(self, f"{title.lower()}_zip", zip_entry)
        return frame
    
    def adjust_color(self, hex_color, amount):
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(max(0, min(255, c + amount)) for c in rgb)
        return '#{:02x}{:02x}{:02x}'.format(*rgb)
    
    def generate_label(self):
        """Generate the label with full backend integration"""
        # Validate inputs
        sender_zip = self.sender_zip.get().strip()
        receiver_zip = self.receiver_zip.get().strip()
        tracking = self.tracking_entry.get().strip().upper().replace(" ", "")
        
        # Validation
        errors = []
        if not sender_zip or len(sender_zip) != 5 or not sender_zip.isdigit():
            errors.append("Sender ZIP must be 5 digits")
        if not receiver_zip or len(receiver_zip) != 5 or not receiver_zip.isdigit():
            errors.append("Receiver ZIP must be 5 digits")
        
        if self.carrier == "UPS":
            if not tracking or len(tracking) != 18 or not tracking.startswith("1Z"):
                errors.append("UPS tracking must be 18 chars starting with 1Z")
        elif self.carrier == "USPS":
            if not tracking or len(tracking) != 22 or not tracking.isdigit():
                errors.append("USPS tracking must be 22 digits")
        elif self.carrier == "FEDEX":
            if not tracking or len(tracking) < 12 or not tracking.isdigit():
                errors.append("FedEx tracking must be 12+ digits")
        
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return
        
        self.status_label.configure(text="Generating label...", text_color="gray")
        self.progress.grid(row=1, column=0, pady=(10, 0), sticky="ew")
        self.progress.start()
        self.generate_btn.configure(state="disabled")
        
        # Run in background
        thread = threading.Thread(
            target=self._do_generate,
            args=(sender_zip, receiver_zip, tracking)
        )
        thread.start()
    
    def _do_generate(self, sender_zip, receiver_zip, tracking):
        """Background label generation with real backend"""
        try:
            from ftid_gen.address_utils import get_zipcode_info_from_file_or_api, generate_fake_address, search_yelp_for_address, generate_full_name
            from ftid_gen.tracking_utils import modify_tracking_number, modify_usps_tracking_number, modify_fedex_tracking_number
            from ftid_gen.label_processor import process_label
            from ftid_gen.config import TEMPLATES
            
            use_real = self.address_type_var.get() == "real"
            
            # Generate sender address
            sender_info = generate_fake_address(sender_zip) if not use_real else (search_yelp_for_address(sender_zip) or generate_fake_address(sender_zip))
            sender_info['name'] = generate_full_name()
            
            # Generate receiver address
            receiver_info = generate_fake_address(receiver_zip) if not use_real else (search_yelp_for_address(receiver_zip) or generate_fake_address(receiver_zip))
            receiver_info['name'] = generate_full_name()
            
            # Modify tracking
            if self.carrier == "UPS":
                modified_tracking = modify_tracking_number(tracking)
                method = "FTID_UPS"
                template_key = "4"
            elif self.carrier == "USPS":
                modified_tracking = modify_usps_tracking_number(tracking)
                method = "FTID_USPS"
                template_key = "5"
            else:
                modified_tracking = modify_fedex_tracking_number(tracking)
                method = "FTID_FEDEX"
                template_key = "6"
            
            tracking_bar = tracking
            if self.carrier == "FEDEX":
                tracking_bar = f"{FEDEX_TRACKING_PREFIX}{tracking}"

            # Create FTID info - note: address generators return 'address' not 'street'
            ftid_info = {
                'sender': sender_info['name'],
                'sender_address': sender_info.get('address', sender_info.get('street', '')),
                'sender_2nd_line': f"{sender_info.get('city', '')} {sender_info.get('state', '')} {sender_info.get('zip_code', sender_info.get('zip', sender_zip))}",
                'receiver': receiver_info['name'],
                'receiver_address': receiver_info.get('address', receiver_info.get('street', '')),
                'receiver_2nd_line': f"{receiver_info.get('city', '')} {receiver_info.get('state', '')} {receiver_info.get('zip_code', receiver_info.get('zip', receiver_zip))}",
                'tracking_number': modified_tracking,
                'tracking_bar': tracking_bar,
                'original_tracking': tracking,
                'sender_zip': sender_zip,
                'receiver_zip': receiver_zip,
            }
            
            # Get template - use same directory as gui_app.py
            name, _, template = TEMPLATES[template_key]
            project_dir = os.path.dirname(os.path.abspath(__file__))
            # Template path already includes 'ftid_gen/' so join directly with project dir
            template_path = os.path.join(project_dir, template)
            script_dir = project_dir
            
            # Generate label - process_label returns (barcode_img, output_path)
            barcode_img, label_output_path = process_label(name, tracking_bar, template_path, script_dir, ftid_info)
            
            # Save to CSV
            self._save_to_csv(ftid_info, method)
            
            self.after(0, self._generation_complete, True, f"Label saved to:\n{label_output_path}", label_output_path)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, self._generation_complete, False, str(e), None)
    
    def _save_to_csv(self, ftid_info, method):
        """Save run to CSV log"""
        try:
            os.makedirs(os.path.dirname(CSV_LOG_PATH), exist_ok=True)
            file_exists = os.path.exists(CSV_LOG_PATH)
            
            with open(CSV_LOG_PATH, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['timestamp', 'method', 'tracking_number', 'original_tracking', 
                             'sender', 'sender_address', 'sender_city_state_zip',
                             'receiver', 'receiver_address', 'receiver_city_state_zip']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'method': method,
                    'tracking_number': ftid_info.get('tracking_number', ''),
                    'original_tracking': ftid_info.get('original_tracking', ''),
                    'sender': ftid_info.get('sender', ''),
                    'sender_address': ftid_info.get('sender_address', ''),
                    'sender_city_state_zip': ftid_info.get('sender_2nd_line', ''),
                    'receiver': ftid_info.get('receiver', ''),
                    'receiver_address': ftid_info.get('receiver_address', ''),
                    'receiver_city_state_zip': ftid_info.get('receiver_2nd_line', ''),
                })
        except Exception as e:
            print(f"⚠️ Could not save CSV history: {e}")
    
    def _generation_complete(self, success, message, label_path):
        """Handle generation completion"""
        self.progress.stop()
        self.progress.grid_forget()
        self.generate_btn.configure(state="normal")
        
        if success:
            self.status_label.configure(text="✓ Label generated successfully!", text_color="green")
            
            # Show success dialog with option to view
            result = messagebox.askyesno(
                "Success! 🎉",
                f"{message}\n\nWould you like to open the label?"
            )
            if result:
                if label_path:
                    path_str = str(label_path)
                    
                    if os.path.exists(path_str):
                        import subprocess
                        try:
                            subprocess.run(["open", "-a", "Preview", path_str], check=True)
                        except Exception as e:
                            print(f"⚠️ Could not open label with Preview: {e}")
                            subprocess.run(["open", path_str])
                    else:
                        messagebox.showwarning("File Not Found", f"Label file not found at:\n{path_str}")
                else:
                    messagebox.showwarning("No Path", "No label path was returned from generation.")
        else:
            self.status_label.configure(text=f"✗ Error: {message[:50]}...", text_color="red")
            messagebox.showerror("Generation Failed", message)


class HistoryView(ctk.CTkFrame):
    """History view showing previous label runs"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            header_frame,
            text="📋 Label History",
            font=ctk.CTkFont(size=28, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        
        ctk.CTkButton(
            header_frame,
            text="🔄 Refresh",
            width=100,
            command=self.load_history
        ).grid(row=0, column=2, padx=(10, 0))
        
        # History table
        self.history_scroll = ctk.CTkScrollableFrame(self, corner_radius=12)
        self.history_scroll.grid(row=1, column=0, sticky="nsew")
        self.history_scroll.grid_columnconfigure(0, weight=1)
        
        self.load_history()
    
    def load_history(self):
        """Load and display history from CSV"""
        # Clear existing
        for widget in self.history_scroll.winfo_children():
            widget.destroy()
        
        try:
            if os.path.exists(CSV_LOG_PATH):
                with open(CSV_LOG_PATH, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    
                    if rows:
                        # Header row
                        header = ctk.CTkFrame(self.history_scroll, fg_color=("gray80", "gray25"), corner_radius=8)
                        header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
                        header.grid_columnconfigure((0, 1, 2, 3), weight=1)
                        
                        for i, col in enumerate(["Method", "Tracking", "Sender", "Date"]):
                            ctk.CTkLabel(header, text=col, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=i, padx=15, pady=10)
                        
                        # Data rows - clickable to regenerate
                        for i, row in enumerate(reversed(rows[-50:])):  # Last 50
                            item = ctk.CTkButton(
                                self.history_scroll,
                                corner_radius=8,
                                fg_color=("gray90", "gray20"),
                                hover_color=("gray80", "gray30"),
                                text="",
                                height=50,
                                command=lambda r=row: self._regenerate_from_history(r)
                            )
                            item.grid(row=i+1, column=0, sticky="ew", pady=2)
                            
                            # Create inner frame for layout
                            inner = ctk.CTkFrame(item, fg_color="transparent")
                            inner.place(relx=0, rely=0.5, anchor="w", x=10)
                            
                            method = row.get('method', 'Unknown')
                            icon = {"FTID_UPS": "📦", "FTID_USPS": "📬", "FTID_FEDEX": "🚚"}.get(method, "📋")
                            tracking = row.get('original_tracking', row.get('tracking_number', ''))[:18]
                            
                            ctk.CTkLabel(inner, text=f"{icon} {method}  |  {tracking}...  |  {row.get('timestamp', '')[:16]}",
                                        font=ctk.CTkFont(size=12), fg_color="transparent").pack(side="left")
                    else:
                        self._show_empty()
            else:
                self._show_empty()
        except Exception as e:
            self._show_empty()
    
    def _regenerate_from_history(self, row):
        """Regenerate a label from history with same tracking but new addresses"""
        method = row.get('method', '')
        original_tracking = row.get('original_tracking', row.get('tracking_number', ''))
        
        # Parse ZIPs from city_state_zip strings (format: "City State ZIP")
        sender_csz = row.get('sender_city_state_zip', '')
        receiver_csz = row.get('receiver_city_state_zip', '')
        
        sender_zip = sender_csz.split()[-1] if sender_csz else ''
        receiver_zip = receiver_csz.split()[-1] if receiver_csz else ''
        
        # Determine carrier
        if 'UPS' in method:
            carrier = 'UPS'
        elif 'USPS' in method:
            carrier = 'USPS'
        elif 'FEDEX' in method:
            carrier = 'FEDEX'
        else:
            messagebox.showerror("Error", "Unknown carrier type")
            return
        
        # Confirm regeneration
        result = messagebox.askyesno(
            "Regenerate Label",
            f"Regenerate {carrier} label?\n\n"
            f"Original Tracking: {original_tracking[:20]}...\n"
            f"Sender ZIP: {sender_zip}\n"
            f"Receiver ZIP: {receiver_zip}\n\n"
            "New addresses will be generated."
        )
        
        if result:
            # Pre-populate data storage with values
            try:
                from ftid_gen.data_storage import storage
                storage.save_sender_zip(sender_zip)
                storage.save_receiver_zip(receiver_zip)
                if carrier == 'UPS':
                    storage.save_ups_tracking(original_tracking)
                elif carrier == 'USPS':
                    storage.save_usps_tracking(original_tracking)
                else:
                    storage.save_fedex_tracking(original_tracking)
            except Exception as e:
                print(f"⚠️ Could not save to data storage: {e}")
            
            # Navigate to the appropriate form
            if carrier == 'UPS':
                self.app.show_ups_form()
            elif carrier == 'USPS':
                self.app.show_usps_form()
            else:
                self.app.show_fedex_form()
            
            messagebox.showinfo("Ready", f"Form pre-filled with previous data.\n\nClick 'Generate Label' to create a new label with fresh addresses.")
    
    def _show_empty(self):
        ctk.CTkLabel(
            self.history_scroll,
            text="📭 No history entries yet.\n\nGenerate labels to see them here.",
            font=ctk.CTkFont(size=14),
            text_color="gray",
            justify="center"
        ).grid(row=0, column=0, pady=80)


class ImportView(ctk.CTkFrame):
    """Excel/CSV import view"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        ctk.CTkLabel(
            self,
            text="📁 Import from Excel/CSV",
            font=ctk.CTkFont(size=28, weight="bold")
        ).grid(row=0, column=0, pady=(0, 20), sticky="w")
        
        # Drop zone
        self.drop_zone = ctk.CTkFrame(self, corner_radius=20, height=250)
        self.drop_zone.grid(row=1, column=0, sticky="nsew")
        self.drop_zone.grid_columnconfigure(0, weight=1)
        self.drop_zone.grid_rowconfigure(0, weight=1)
        
        drop_content = ctk.CTkFrame(self.drop_zone, fg_color="transparent")
        drop_content.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(drop_content, text="📄", font=ctk.CTkFont(size=50)).pack(pady=(0, 15))
        ctk.CTkLabel(drop_content, text="Click to select file", font=ctk.CTkFont(size=18, weight="bold")).pack()
        ctk.CTkLabel(drop_content, text="Supports .xlsx, .xls, and .csv files", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(5, 20))
        
        ctk.CTkButton(
            drop_content,
            text="📂 Browse Files",
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.select_file
        ).pack()
        
        self.drop_zone.bind("<Button-1>", lambda e: self.select_file())
    
    def select_file(self):
        """Open file dialog and process import"""
        filename = filedialog.askopenfilename(
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )
        if filename:
            try:
                from ftid_gen.excel_importer import excel_importer
                messagebox.showinfo("File Selected", f"Selected: {os.path.basename(filename)}\n\nImport functionality ready.")
            except Exception as e:
                messagebox.showerror("Import Error", str(e))


class MaxiCodeView(ctk.CTkFrame):
    """MaxiCode management view"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        ctk.CTkLabel(
            self,
            text="🔲 MaxiCode Manager",
            font=ctk.CTkFont(size=28, weight="bold")
        ).grid(row=0, column=0, pady=(0, 10), sticky="w")
        
        ctk.CTkLabel(
            self,
            text="Generate and manage MaxiCode barcodes for UPS labels",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).grid(row=1, column=0, pady=(0, 30), sticky="w")
        
        # Enhanced MaxiCode section
        enhanced_frame = ctk.CTkFrame(self, corner_radius=15)
        enhanced_frame.grid(row=2, column=0, sticky="ew", pady=10)
        enhanced_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            enhanced_frame,
            text="🚀 Enhanced MaxiCode Generator",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, padx=25, pady=(25, 10), sticky="w")
        
        ctk.CTkLabel(
            enhanced_frame,
            text="Generate MaxiCodes with no character limits and advanced options",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        ).grid(row=1, column=0, padx=25, pady=(0, 20), sticky="w")
        
        ctk.CTkButton(
            enhanced_frame,
            text="Open Enhanced Generator →",
            height=50,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#4a1f75",
            command=self.open_enhanced
        ).grid(row=2, column=0, padx=25, pady=(0, 25), sticky="ew")
        
        # Previous entries section
        prev_frame = ctk.CTkFrame(self, corner_radius=15)
        prev_frame.grid(row=3, column=0, sticky="ew", pady=10)
        prev_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            prev_frame,
            text="📋 Previous MaxiCode Entries",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, padx=25, pady=(25, 10), sticky="w")
        
        ctk.CTkLabel(
            prev_frame,
            text="Quickly reuse previously generated MaxiCode data",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        ).grid(row=1, column=0, padx=25, pady=(0, 20), sticky="w")
        
        ctk.CTkButton(
            prev_frame,
            text="View Previous Entries →",
            height=50,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#374151",
            command=self.view_previous
        ).grid(row=2, column=0, padx=25, pady=(0, 25), sticky="ew")
    
    def open_enhanced(self):
        messagebox.showinfo("Enhanced MaxiCode", "Opening enhanced MaxiCode generator...\n\nThis will launch the terminal-based enhanced generator.")
        # Could integrate the enhanced_maxicode module here
    
    def view_previous(self):
        messagebox.showinfo("Previous Entries", "Loading previous MaxiCode entries...")


class SettingsView(ctk.CTkFrame):
    """Settings view with full integration"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        
        # Header
        ctk.CTkLabel(
            self,
            text="⚙️ Settings",
            font=ctk.CTkFont(size=28, weight="bold")
        ).grid(row=0, column=0, pady=(0, 25), sticky="w")
        
        # Settings sections
        self.widgets = {}
        
        # From Address section
        self.create_from_address_section(row=1)
        
        # MaxiCode settings
        self.create_maxicode_section(row=2)

        # Layout preview
        self.create_preview_section(row=3)
        
        # Save button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, pady=(20, 0), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkButton(
            btn_frame,
            text="💾 Save Settings",
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#2d5a27",
            command=self.save_settings
        ).grid(row=0, column=0, sticky="ew")
        
        self.status_label = ctk.CTkLabel(btn_frame, text="", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=1, column=0, pady=(10, 0))
        
        # Load current settings
        self.load_settings()
    
    def create_from_address_section(self, row):
        """Create default from address section"""
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.grid(row=row, column=0, sticky="ew", pady=8)
        frame.grid_columnconfigure((1, 2, 3), weight=1)
        
        ctk.CTkLabel(
            frame,
            text="📍 Default From Address",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=4, padx=20, pady=(20, 15), sticky="w")
        
        fields = [("ZIP Code", "zip_code"), ("City", "city"), ("State", "state")]
        for i, (label, key) in enumerate(fields):
            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=12)).grid(row=1, column=i, padx=(20 if i == 0 else 10, 10), pady=(0, 5), sticky="w")
            entry = ctk.CTkEntry(frame, height=40)
            entry.grid(row=2, column=i, padx=(20 if i == 0 else 10, 10 if i < 2 else 20), pady=(0, 20), sticky="ew")
            self.widgets[f"from_{key}"] = entry
    
    def create_maxicode_section(self, row):
        """Create MaxiCode settings section"""
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.grid(row=row, column=0, sticky="ew", pady=8)
        frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            frame,
            text="🔲 MaxiCode Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 15), sticky="w")
        
        # Auto-generate switch
        ctk.CTkLabel(frame, text="Auto-generate MaxiCode", font=ctk.CTkFont(size=13)).grid(row=1, column=0, padx=20, pady=10, sticky="w")
        auto_switch = ctk.CTkSwitch(frame, text="")
        auto_switch.grid(row=1, column=1, padx=20, pady=10, sticky="w")
        self.widgets["maxicode_auto"] = auto_switch
        
        # No limit switch
        ctk.CTkLabel(frame, text="No character limit", font=ctk.CTkFont(size=13)).grid(row=2, column=0, padx=20, pady=(0, 20), sticky="w")
        limit_switch = ctk.CTkSwitch(frame, text="")
        limit_switch.grid(row=2, column=1, padx=20, pady=(0, 20), sticky="w")
        self.widgets["maxicode_nolimit"] = limit_switch

    def create_preview_section(self, row):
        """Live label preview using the same Python compositor as generation."""
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.grid(row=row, column=0, sticky="nsew", pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            frame,
            text="👁 Label Layout Preview",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        controls = ctk.CTkFrame(frame, fg_color="transparent")
        controls.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        controls.grid_columnconfigure(2, weight=1)

        self.preview_carrier = ctk.StringVar(value="UPS")
        ctk.CTkOptionMenu(
            controls,
            values=["UPS", "USPS", "FEDEX"],
            variable=self.preview_carrier,
            command=lambda _: self.refresh_preview(),
            width=120,
        ).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(
            controls,
            text="Refresh Preview",
            width=140,
            command=self.refresh_preview,
        ).grid(row=0, column=1, padx=(0, 10))

        self.preview_status = ctk.CTkLabel(controls, text="", font=ctk.CTkFont(size=12), text_color="gray")
        self.preview_status.grid(row=0, column=2, sticky="w")

        self.preview_image_label = ctk.CTkLabel(frame, text="Loading preview…")
        self.preview_image_label.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")

        self.after(250, self.refresh_preview)

    def refresh_preview(self):
        """Render a composite preview off the UI thread."""
        self.preview_status.configure(text="Updating preview…", text_color="gray")

        def worker():
            try:
                from ftid_gen.label_processor import compose_label
                from ftid_gen.address_utils import generate_fake_address, generate_full_name
                from ftid_gen.tracking_utils import modify_tracking_number
                from ftid_gen.config import BASE_DIR, TEMPLATES
                import tempfile

                carrier = self.preview_carrier.get().upper()
                method_map = {
                    "UPS": ("FTID_UPS", "4", "1Z9999999999999999"),
                    "USPS": ("FTID_USPS", "5", "4201234567890123456789"),
                    "FEDEX": ("FTID_FEDEX", "6", "123456789012"),
                }
                method, template_key, sample_tracking = method_map[carrier]
                default_template = os.path.join(str(BASE_DIR), TEMPLATES[template_key][2])

                sample_zip = "10001"
                address = generate_fake_address(sample_zip)
                modified_tracking = modify_tracking_number(sample_tracking) if carrier == "UPS" else sample_tracking
                ftid_info = {
                    "sender": generate_full_name(),
                    "sender_address": address["address"],
                    "sender_2nd_line": f"{address['city']} {address['state']} {address['zip_code']}",
                    "receiver": generate_full_name(),
                    "receiver_address": address["address"],
                    "receiver_2nd_line": f"{address['city']} {address['state']} {address['zip_code']}",
                    "tracking_number": modified_tracking,
                    "tracking_bar": sample_tracking,
                    "receiver_zip": address.get("zip_code", sample_zip),
                    "sender_zip": sample_zip,
                    "original_tracking": sample_tracking,
                }

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
                    output_path = handle.name

                compose_label(
                    method,
                    ftid_info["tracking_bar"],
                    default_template,
                    ftid_info=ftid_info,
                    label_layout=settings.get("label_layout", {}),
                    output_path=output_path,
                )

                image = Image.open(output_path)
                max_width = 520
                ratio = min(1.0, max_width / max(image.width, 1))
                display_size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
                preview_image = image.resize(display_size)
                ctk_image = ctk.CTkImage(light_image=preview_image, dark_image=preview_image, size=display_size)
                self.after(0, lambda: self._show_preview_image(ctk_image, display_size))
            except Exception as exc:
                self.after(0, lambda: self.preview_status.configure(text=f"Preview failed: {exc}", text_color="red"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_preview_image(self, ctk_image, display_size):
        self.preview_image_label.configure(image=ctk_image, text="")
        self.preview_image_label.image = ctk_image
        self.preview_status.configure(
            text=f"Preview matches generation output ({display_size[0]}×{display_size[1]} px)",
            text_color="green",
        )
    
    def load_settings(self):
        """Load current settings into widgets"""
        try:
            from_addr = settings.get_from_address()
            self.widgets["from_zip_code"].insert(0, from_addr.get("zip_code", ""))
            self.widgets["from_city"].insert(0, from_addr.get("city", ""))
            self.widgets["from_state"].insert(0, from_addr.get("state", ""))
            
            if settings.get("maxicode.auto_generate", True):
                self.widgets["maxicode_auto"].select()
            if settings.get("maxicode.no_character_limit", True):
                self.widgets["maxicode_nolimit"].select()
        except Exception as e:
            print(f"⚠️ Could not load settings: {e}")
    
    def save_settings(self):
        """Save settings"""
        try:
            # Save from address
            settings.set("from_address.zip_code", self.widgets["from_zip_code"].get())
            settings.set("from_address.city", self.widgets["from_city"].get())
            settings.set("from_address.state", self.widgets["from_state"].get())
            
            # Save MaxiCode settings
            settings.set("maxicode.auto_generate", self.widgets["maxicode_auto"].get() == 1)
            settings.set("maxicode.no_character_limit", self.widgets["maxicode_nolimit"].get() == 1)
            
            self.status_label.configure(text="✓ Settings saved successfully!", text_color="green")
        except Exception as e:
            self.status_label.configure(text=f"✗ Error: {str(e)}", text_color="red")


class TrackingDashboardView(ctk.CTkFrame):
    """Package tracking dashboard view"""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.filter_carrier = "ALL"
        self.filter_status = "ALL"
        self.search_query = ""
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            header_frame,
            text="📊 Package Tracker",
            font=ctk.CTkFont(size=28, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        
        # Stats bar
        self.stats_label = ctk.CTkLabel(
            header_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.stats_label.grid(row=0, column=1, padx=20, sticky="e")
        
        btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=2, sticky="e")
        
        ctk.CTkButton(
            btn_frame, text="🔄 Refresh", width=90, height=32,
            font=ctk.CTkFont(size=12),
            command=self.refresh_all
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            btn_frame, text="+ Add", width=70, height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#0d6efd",
            command=self.show_add_dialog
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            btn_frame, text="📥 Import Sheet", width=110, height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#198754",
            command=self.import_from_sheet
        ).pack(side="left")
        
        # Filters row
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        filter_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(filter_frame, text="Search:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 5))
        self.search_entry = ctk.CTkEntry(filter_frame, placeholder_text="Tracking, label, store...", height=32, width=220)
        self.search_entry.grid(row=0, column=1, padx=(0, 10), sticky="w")
        self.search_entry.bind("<Return>", lambda e: self._apply_filters())
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filters())
        
        ctk.CTkLabel(filter_frame, text="Carrier:", font=ctk.CTkFont(size=12)).grid(row=0, column=2, padx=(10, 5))
        self.carrier_menu = ctk.CTkOptionMenu(
            filter_frame, values=["ALL", "UPS", "USPS", "FEDEX"],
            width=90, height=32, command=self._on_carrier_filter
        )
        self.carrier_menu.grid(row=0, column=3, padx=(0, 10))
        
        ctk.CTkLabel(filter_frame, text="Status:", font=ctk.CTkFont(size=12)).grid(row=0, column=4, padx=(10, 5))
        self.status_menu = ctk.CTkOptionMenu(
            filter_frame, values=["ALL", "Active", "Delivered", "Exception"],
            width=100, height=32, command=self._on_status_filter
        )
        self.status_menu.grid(row=0, column=5)
        
        # Tracking list
        self.list_frame = ctk.CTkScrollableFrame(self, corner_radius=12, fg_color=("gray95", "gray13"))
        self.list_frame.grid(row=2, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        
        self.load_entries()
    
    def load_entries(self):
        """Load and display tracking entries"""
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        
        try:
            from ftid_gen.package_tracker import tracking_manager
            entries = tracking_manager.get_all()
            
            # Apply filters
            if self.filter_carrier != "ALL":
                entries = [e for e in entries if e.carrier == self.filter_carrier]
            if self.filter_status == "Active":
                entries = [e for e in entries if e.is_active]
            elif self.filter_status == "Delivered":
                entries = [e for e in entries if e.status == "delivered"]
            elif self.filter_status == "Exception":
                entries = [e for e in entries if e.status == "exception"]
            if self.search_query:
                q = self.search_query.lower()
                entries = [e for e in entries if q in e.tracking_number.lower() or q in e.label.lower() or q in e.store.lower()]
            
            # Update stats
            stats = tracking_manager.get_stats()
            self.stats_label.configure(
                text=f"Total: {stats['total']} | Active: {stats['active']} | Delivered: {stats['delivered']} | Exception: {stats['exception']}"
            )
            
            if not entries:
                ctk.CTkLabel(
                    self.list_frame,
                    text="No tracking entries found.\n\nAdd a tracking number or import from Google Sheet.",
                    font=ctk.CTkFont(size=14), text_color="gray", justify="center"
                ).grid(row=0, column=0, pady=60)
                return
            
            for i, entry in enumerate(entries):
                self._create_entry_card(entry, i)
                
        except Exception as e:
            ctk.CTkLabel(
                self.list_frame,
                text=f"Error loading tracking data: {e}",
                font=ctk.CTkFont(size=13), text_color="red"
            ).grid(row=0, column=0, pady=30)
    
    def _create_entry_card(self, entry, row):
        """Create a card widget for a tracking entry"""
        card = ctk.CTkFrame(self.list_frame, corner_radius=10, height=90)
        card.grid(row=row, column=0, pady=4, sticky="ew")
        card.grid_columnconfigure(1, weight=1)
        
        # Carrier color indicator
        carrier_colors = {"UPS": "#351C15", "USPS": "#004B87", "FEDEX": "#4D148C"}
        indicator = ctk.CTkFrame(card, width=5, fg_color=carrier_colors.get(entry.carrier, "gray"))
        indicator.grid(row=0, column=0, rowspan=2, sticky="ns", padx=(0, 8))
        
        # Top row: carrier + tracking + status badge
        top_frame = ctk.CTkFrame(card, fg_color="transparent")
        top_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=(8, 0))
        top_frame.grid_columnconfigure(1, weight=1)
        
        carrier_icons = {"UPS": "📦", "USPS": "📬", "FEDEX": "🚚"}
        ctk.CTkLabel(
            top_frame,
            text=f"{carrier_icons.get(entry.carrier, '📋')} {entry.carrier}",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, padx=(0, 10))
        
        tracking_display = entry.tracking_number[:20] + ("..." if len(entry.tracking_number) > 20 else "")
        ctk.CTkLabel(
            top_frame, text=tracking_display,
            font=ctk.CTkFont(size=12), text_color="gray"
        ).grid(row=0, column=1, sticky="w")
        
        # Status badge
        status_colors = {
            "pending": ("gray", "white"),
            "in_transit": ("#0d6efd", "white"),
            "out_for_delivery": ("#fd7e14", "white"),
            "delivered": ("#198754", "white"),
            "exception": ("#dc3545", "white"),
        }
        bg, fg = status_colors.get(entry.status, ("gray", "white"))
        status_text = entry.status.replace("_", " ").title()
        badge = ctk.CTkLabel(top_frame, text=f" {status_text} ", font=ctk.CTkFont(size=11), fg_color=bg, text_color=fg, corner_radius=6)
        badge.grid(row=0, column=2, padx=(10, 0))
        
        # Bottom row: details + actions
        bottom_frame = ctk.CTkFrame(card, fg_color="transparent")
        bottom_frame.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 8))
        
        detail_parts = []
        if entry.label:
            detail_parts.append(entry.label)
        if entry.store:
            detail_parts.append(entry.store)
        if entry.status_details:
            detail_parts.append(entry.status_details[:50])
        if entry.last_updated:
            detail_parts.append(entry.last_updated[:16])
        
        ctk.CTkLabel(
            bottom_frame,
            text=" | ".join(detail_parts) if detail_parts else "No details",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w"
        ).pack(side="left", fill="x", expand=True)
        
        # Action buttons
        actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        actions_frame.grid(row=0, column=2, rowspan=2, padx=10, pady=8)
        
        ctk.CTkButton(
            actions_frame, text="Track", width=60, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#0d6efd",
            command=lambda e=entry: self._open_tracking_url(e)
        ).pack(pady=(0, 3))
        
        ctk.CTkButton(
            actions_frame, text="Details", width=60, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#6c757d",
            command=lambda e=entry: self._show_detail(e)
        ).pack(pady=(0, 3))
        
        ctk.CTkButton(
            actions_frame, text="Remove", width=60, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#dc3545",
            command=lambda e=entry: self._remove_entry(e)
        ).pack()
    
    def _open_tracking_url(self, entry):
        """Open carrier tracking URL in browser"""
        url = entry.tracking_url
        if url:
            import subprocess
            subprocess.run(["open", url])
        else:
            messagebox.showwarning("No URL", f"No tracking URL available for {entry.carrier}")
    
    def _show_detail(self, entry):
        """Show detail popup with status timeline"""
        detail_win = ctk.CTkToplevel(self)
        detail_win.title(f"Tracking Details - {entry.tracking_number[:20]}")
        detail_win.geometry("500x550")
        detail_win.grab_set()
        
        # Header
        ctk.CTkLabel(
            detail_win, text=f"{entry.carrier} Tracking",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(20, 5))
        
        ctk.CTkLabel(
            detail_win, text=entry.tracking_number,
            font=ctk.CTkFont(size=14), text_color="gray"
        ).pack()
        
        if entry.label:
            ctk.CTkLabel(detail_win, text=entry.label, font=ctk.CTkFont(size=13)).pack(pady=(5, 0))
        if entry.store:
            ctk.CTkLabel(detail_win, text=entry.store, font=ctk.CTkFont(size=12), text_color="gray").pack()
        
        # Current status
        status_colors = {
            "pending": "gray", "in_transit": "#0d6efd",
            "out_for_delivery": "#fd7e14", "delivered": "#198754", "exception": "#dc3545"
        }
        ctk.CTkLabel(
            detail_win,
            text=f"Current Status: {entry.status.replace('_', ' ').title()}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=status_colors.get(entry.status, "gray")
        ).pack(pady=(15, 5))
        
        if entry.status_details:
            ctk.CTkLabel(detail_win, text=entry.status_details, font=ctk.CTkFont(size=12)).pack()
        
        # Timeline
        ctk.CTkLabel(detail_win, text="Status Timeline", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(20, 5))
        
        timeline_frame = ctk.CTkScrollableFrame(detail_win, height=200)
        timeline_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        if entry.history:
            for i, h in enumerate(reversed(entry.history)):
                item = ctk.CTkFrame(timeline_frame, corner_radius=8)
                item.pack(fill="x", pady=2)
                
                status_text = h.status.replace("_", " ").title()
                ctk.CTkLabel(item, text=f"● {status_text}", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=10, pady=(5, 0))
                if h.details:
                    ctk.CTkLabel(item, text=h.details, font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=20)
                info_parts = []
                if h.location:
                    info_parts.append(h.location)
                if h.timestamp:
                    info_parts.append(h.timestamp[:16])
                if info_parts:
                    ctk.CTkLabel(item, text=" | ".join(info_parts), font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", padx=20, pady=(0, 5))
        else:
            ctk.CTkLabel(timeline_frame, text="No history yet", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=20)
        
        # Track on carrier button
        if entry.tracking_url:
            ctk.CTkButton(
                detail_win, text=f"Open on {entry.carrier} Website",
                height=40, fg_color="#0d6efd",
                command=lambda: subprocess.run(["open", entry.tracking_url])
            ).pack(pady=(0, 10), padx=20, fill="x")
        
        ctk.CTkButton(detail_win, text="Close", command=detail_win.destroy, height=35).pack(pady=(0, 15))
    
    def _remove_entry(self, entry):
        """Remove a tracking entry"""
        result = messagebox.askyesno("Remove Entry", f"Remove tracking for {entry.tracking_number[:20]}?")
        if result:
            try:
                from ftid_gen.package_tracker import tracking_manager
                tracking_manager.remove_entry(entry.id)
                self.load_entries()
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def _on_carrier_filter(self, choice):
        self.filter_carrier = choice
        self._apply_filters()
    
    def _on_status_filter(self, choice):
        self.filter_status = choice
        self._apply_filters()
    
    def _apply_filters(self):
        self.search_query = self.search_entry.get().strip()
        self.load_entries()
    
    def refresh_all(self):
        """Refresh all tracking statuses"""
        self.stats_label.configure(text="Refreshing statuses...", text_color="gray")
        self.load_entries()
        
        def do_refresh():
            try:
                from ftid_gen.tracking_fetcher import tracking_fetcher
                from ftid_gen.package_tracker import tracking_manager
                active = tracking_manager.get_active()
                updated = 0
                for entry in active:
                    result = tracking_fetcher.fetch_status(entry)
                    if result and result.get("status") and result["status"] != entry.status:
                        tracking_manager.update_status(
                            entry.id, status=result["status"],
                            details=result.get("details", ""),
                            location=result.get("location", ""),
                        )
                        updated += 1
                self.after(0, lambda: self._refresh_complete(updated))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Refresh Error", str(e)))
        
        threading.Thread(target=do_refresh, daemon=True).start()
    
    def _refresh_complete(self, updated_count):
        self.load_entries()
        if updated_count > 0:
            messagebox.showinfo("Refresh Complete", f"{updated_count} package(s) updated.")
    
    def show_add_dialog(self):
        """Show dialog to add a tracking entry manually"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Tracking Entry")
        dialog.geometry("400x420")
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Add Tracking Number", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 15))
        
        fields = {}
        for label_text, placeholder in [
            ("Tracking Number *", "Enter tracking number"),
            ("Label", "e.g. ali - dolphin rc"),
            ("Store / Seller", "e.g. aliexpress"),
            ("Origin ZIP", "5-digit ZIP"),
            ("Destination ZIP", "5-digit ZIP"),
        ]:
            ctk.CTkLabel(dialog, text=label_text, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=30, pady=(10, 0))
            entry = ctk.CTkEntry(dialog, placeholder_text=placeholder, height=35)
            entry.pack(padx=30, fill="x")
            fields[label_text] = entry
        
        ctk.CTkLabel(dialog, text="Carrier", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=30, pady=(10, 0))
        carrier_var = ctk.StringVar(value="Auto-detect")
        carrier_menu = ctk.CTkOptionMenu(dialog, variable=carrier_var, values=["Auto-detect", "UPS", "USPS", "FEDEX"])
        carrier_menu.pack(padx=30, fill="x")
        
        def add():
            tracking = fields["Tracking Number *"].get().strip()
            if not tracking:
                messagebox.showerror("Error", "Tracking number is required.")
                return
            carrier = carrier_var.get()
            if carrier == "Auto-detect":
                carrier = "UNKNOWN"
            try:
                from ftid_gen.package_tracker import tracking_manager
                tracking_manager.add_entry(
                    tracking_number=tracking,
                    carrier=carrier,
                    label=fields["Label"].get().strip(),
                    store=fields["Store / Seller"].get().strip(),
                    origin_zip=fields["Origin ZIP"].get().strip(),
                    destination_zip=fields["Destination ZIP"].get().strip(),
                )
                dialog.destroy()
                self.load_entries()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        ctk.CTkButton(dialog, text="Add Entry", height=40, fg_color="#0d6efd", command=add).pack(pady=20, padx=30, fill="x")
        ctk.CTkButton(dialog, text="Cancel", height=35, fg_color="gray", command=dialog.destroy).pack(padx=30, fill="x")
    
    def import_from_sheet(self):
        """Import tracking data from Google Sheet"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Import from Google Sheet")
        dialog.geometry("500x400")
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Import from Google Sheet", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 10))
        ctk.CTkLabel(
            dialog,
            text="Paste your Google Sheet data below.\nUse tab-separated values (copy from Google Sheets directly).",
            font=ctk.CTkFont(size=12), text_color="gray", justify="center"
        ).pack(pady=(0, 15))
        
        ctk.CTkLabel(dialog, text="Column Headers (auto-mapped):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=20)
        ctk.CTkLabel(
            dialog,
            text="Action | What | Store | Seller | Total | Payment | Email | Where | Method 1 | Tracking | URL | To | From | Tracking 2 | ...",
            font=ctk.CTkFont(size=10), text_color="gray", wraplength=450
        ).pack(anchor="w", padx=20, pady=(0, 10))
        
        text_box = ctk.CTkTextbox(dialog, height=150)
        text_box.pack(padx=20, fill="x")
        
        status_label = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=12))
        status_label.pack(pady=(10, 0))
        
        def do_import():
            raw = text_box.get("1.0", "end").strip()
            if not raw:
                messagebox.showerror("Error", "Paste sheet data first.")
                return
            
            lines = raw.strip().split("\n")
            if len(lines) < 2:
                messagebox.showerror("Error", "Need at least a header row and one data row.")
                return
            
            headers = lines[0].split("\t")
            rows = []
            for line in lines[1:]:
                values = line.split("\t")
                row = {}
                for i, h in enumerate(headers):
                    if i < len(values):
                        row[h.strip()] = values[i].strip()
                rows.append(row)
            
            try:
                from ftid_gen.package_tracker import tracking_manager
                added = tracking_manager.import_from_sheet_rows(rows)
                status_label.configure(text=f"✅ Imported {len(added)} tracking entries!", text_color="green")
                self.load_entries()
                dialog.after(1500, dialog.destroy)
            except Exception as e:
                status_label.configure(text=f"❌ Error: {e}", text_color="red")
        
        ctk.CTkButton(dialog, text="Import", height=40, fg_color="#198754", command=do_import).pack(pady=(15, 0), padx=20, fill="x")
        ctk.CTkButton(dialog, text="Cancel", height=35, fg_color="gray", command=dialog.destroy).pack(pady=(5, 10), padx=20, fill="x")


def main():
    """Launch the GUI application"""
    app = FTIDApp()
    app.mainloop()


if __name__ == "__main__":
    main()
