import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from ftid_gen.settings_manager import settings

class PreviousMaxicodeManager:
    """Manages previous Maxicode entries for quick insertion"""
    
    def __init__(self, history_file: str = "previous_maxicode.json"):
        self.history_file = history_file
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """Load previous Maxicode history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load Maxicode history: {e}")
        return []
    
    def _save_history(self):
        """Save Maxicode history to file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save Maxicode history: {e}")
    
    def add_maxicode(self, maxicode_data: str, method: str, tracking_number: str, 
                    sender_info: Dict[str, str], receiver_info: Dict[str, str]):
        """Add a new Maxicode entry to history"""
        if not settings.get('previous_maxicode.enabled', True):
            return
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'maxicode_data': maxicode_data,
            'method': method,
            'tracking_number': tracking_number,
            'sender_info': sender_info,
            'receiver_info': receiver_info,
            'preview': self._generate_preview(maxicode_data, method, tracking_number)
        }
        
        # Add to beginning of list
        self.history.insert(0, entry)
        
        # Keep only the configured number of entries
        max_entries = settings.get('previous_maxicode.max_entries', 3)
        if len(self.history) > max_entries:
            self.history = self.history[:max_entries]
        
        self._save_history()
    
    def _generate_preview(self, maxicode_data: str, method: str, tracking_number: str) -> str:
        """Generate a preview string for the Maxicode entry"""
        # Truncate maxicode data for preview
        preview_data = maxicode_data[:20] + "..." if len(maxicode_data) > 20 else maxicode_data
        
        return f"{method} | {tracking_number} | {preview_data}"
    
    def get_recent_entries(self) -> List[Dict[str, Any]]:
        """Get recent Maxicode entries"""
        if not settings.get('previous_maxicode.enabled', True):
            return []
        
        max_entries = settings.get('previous_maxicode.max_entries', 3)
        return self.history[:max_entries]
    
    def show_recent_entries_menu(self) -> Optional[Dict[str, Any]]:
        """Show menu for selecting recent Maxicode entries"""
        entries = self.get_recent_entries()
        
        if not entries:
            print("No previous Maxicode entries found.")
            return None
        
        print("\n" + "="*60)
        print("📋 PREVIOUS MAXICODE ENTRIES")
        print("="*60)
        
        for i, entry in enumerate(entries, 1):
            print(f"{i}. {entry['preview']}")
            if settings.get('previous_maxicode.show_preview', True):
                print(f"   Method: {entry['method']}")
                print(f"   Tracking: {entry['tracking_number']}")
                print(f"   Sender: {entry['sender_info'].get('name', 'N/A')}")
                print(f"   Receiver: {entry['receiver_info'].get('name', 'N/A')}")
                print(f"   Date: {entry['timestamp'][:10]}")
                print()
        
        print("0. Cancel")
        
        while True:
            try:
                choice = input("\nSelect an entry to reuse (or 0 to cancel, or press Enter for first): ").strip()
                if not choice:
                    choice = "1"
                if choice == "0":
                    return None
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(entries):
                    return entries[choice_num - 1]
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a valid number.")
    
    def clear_history(self):
        """Clear all Maxicode history"""
        self.history = []
        self._save_history()
        print("✅ Maxicode history cleared.")
    
    def get_entry_by_tracking(self, tracking_number: str) -> Optional[Dict[str, Any]]:
        """Find a Maxicode entry by tracking number"""
        for entry in self.history:
            if entry['tracking_number'] == tracking_number:
                return entry
        return None
    
    def update_entry(self, tracking_number: str, new_data: Dict[str, Any]):
        """Update an existing Maxicode entry"""
        for entry in self.history:
            if entry['tracking_number'] == tracking_number:
                entry.update(new_data)
                entry['timestamp'] = datetime.now().isoformat()
                entry['preview'] = self._generate_preview(
                    entry['maxicode_data'], 
                    entry['method'], 
                    entry['tracking_number']
                )
                self._save_history()
                break

# Global previous Maxicode manager instance
previous_maxicode = PreviousMaxicodeManager()



