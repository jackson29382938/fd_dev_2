import json
import os
from typing import Any, Dict, Optional

class FTIDDataStorage:
    """Local storage for FTID input data to enable 'use previous' functionality"""
    
    def __init__(self, storage_file: str = "ftid_data.json"):
        self.storage_file = storage_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load data from storage file"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load previous data: {e}")
        return {}
    
    def _save_data(self):
        """Save data to storage file"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save data: {e}")
    
    def get_previous(self, key: str) -> Optional[Any]:
        """Get previous value for a key"""
        return self.data.get(key)
    
    def has_previous(self, key: str) -> bool:
        """Check if previous value exists for a key"""
        return key in self.data and self.data[key] is not None
    
    def save(self, key: str, value: Any):
        """Save a value for a key"""
        self.data[key] = value
        self._save_data()
    
    def get_previous_sender_zip(self) -> Optional[str]:
        return self.get_previous("sender_zip")
    
    def get_previous_receiver_zip(self) -> Optional[str]:
        return self.get_previous("receiver_zip")
    
    def get_previous_ups_tracking(self) -> Optional[str]:
        return self.get_previous("ups_tracking")
    
    def get_previous_usps_tracking(self) -> Optional[str]:
        return self.get_previous("usps_tracking")
    
    def get_previous_fedex_tracking(self) -> Optional[str]:
        return self.get_previous("fedex_tracking")
    
    def get_previous_address_type(self) -> Optional[str]:
        return self.get_previous("address_type")
    
    def save_sender_zip(self, zip_code: str):
        self.save("sender_zip", zip_code)
    
    def save_receiver_zip(self, zip_code: str):
        self.save("receiver_zip", zip_code)
    
    def save_ups_tracking(self, tracking: str):
        self.save("ups_tracking", tracking)
    
    def save_usps_tracking(self, tracking: str):
        self.save("usps_tracking", tracking)
    
    def save_fedex_tracking(self, tracking: str):
        self.save("fedex_tracking", tracking)
    
    def save_address_type(self, address_type: str):
        self.save("address_type", address_type)

# Global storage instance
storage = FTIDDataStorage()
