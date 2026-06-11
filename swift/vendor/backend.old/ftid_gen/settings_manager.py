import json
import os
from typing import Any, Dict
from pathlib import Path


class SettingsManager:
    """Centralized settings management with persistent storage."""

    def __init__(self, settings_file: str = "ftid_settings.json"):
        self.settings_file = Path(settings_file)
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file, merging any missing default keys."""
        defaults = self._get_default_settings()
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._merge_defaults(loaded, defaults)
                return loaded
            except Exception as e:
                print(f"Warning: Could not load settings: {e}")
                self._backup_corrupt_settings()
        return defaults

    def _backup_corrupt_settings(self) -> None:
        """Keep a copy of an unreadable settings file for recovery."""
        backup_path = self.settings_file.with_suffix(
            self.settings_file.suffix + ".corrupt"
        )
        try:
            os.replace(self.settings_file, backup_path)
            print(f"Backed up unreadable settings to {backup_path}")
        except OSError as e:
            print(f"Warning: Could not back up settings file: {e}")

    @staticmethod
    def _merge_defaults(target: Dict[str, Any], defaults: Dict[str, Any]) -> None:
        """Recursively add missing keys from defaults into target."""
        for key, value in defaults.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target[key], dict):
                SettingsManager._merge_defaults(target[key], value)

    @staticmethod
    def _text_block(
        start_x: int,
        start_y: int,
        font_size: int,
        scale: float,
        line_spacing: int,
        char_spacing: float,
        horizontal_squish: float | None = None,
        text: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> Dict[str, Any]:
        block: Dict[str, Any] = {
            "start_x": start_x,
            "start_y": start_y,
            "font_size": font_size,
            "scale": scale,
            "line_spacing": line_spacing,
            "char_spacing": char_spacing,
            "whitespace": 0,
            "width": width,
            "height": height,
            "x_offset": 0,
            "y_offset": 0,
        }
        if horizontal_squish is not None:
            block["horizontal_squish"] = horizontal_squish
        if text is not None:
            block["text"] = text
        return block

    @staticmethod
    def _barcode(whitespace: float, module_height: float, width: int, height: int, x_position: int, y_position: int) -> Dict[str, Any]:
        return {
            "whitespace": whitespace,
            "module_height": module_height,
            "width": width,
            "height": height,
            "x_position": x_position,
            "y_position": y_position,
            "scale": 1.0,
            "x_offset": 0,
            "y_offset": 0,
        }

    @staticmethod
    def _maxicode() -> Dict[str, Any]:
        return {
            "whitespace": 0,
            "width": 312,
            "height": 288,
            "x_offset": 42,
            "y_offset": -1144,
            "x_position": 42,
            "y_position": None,
            "scale": 2.0,
        }

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings configuration."""
        return {
            "from_address": {"zip_code": "", "city": "", "state": ""},
            "maxicode": {
                "auto_generate": True,
                "no_character_limit": True,
                "manual_mode": False,
                "prompt_input_method": False,
            },
            "input_fields": {
                "show_sender_name": True,
                "show_sender_address": True,
                "show_receiver_name": True,
                "show_receiver_address": True,
                "show_receiver_zip": True,
                "show_tracking_number": True,
            },
            "file_import": {
                "default_format": "excel",
                "auto_detect_columns": True,
                "batch_processing": True,
            },
            "previous_maxicode": {
                "enabled": True,
                "max_entries": 3,
                "show_preview": True,
            },
            "zip_lookup": {
                "auto_identify": True,
                "use_api_fallback": True,
                "cache_results": True,
            },
            "ui": {
                "show_tooltips": True,
                "compact_mode": False,
                "theme": "default",
            },
            "label_layout": {
                "ups": {
                    "custom_template_path": None,
                    "template_mask": {
                        "enabled": True,
                        "x_position": 0,
                        "y_position": 585,
                        "width": 405,
                        "height": 375,
                        "opacity": 0.9,
                        "scale": 1.0,
                        "whitespace": 0,
                    },
                    "maxicode": self._maxicode(),
                    "barcode": self._barcode(6.5, 15.0, 970, 300, 90, 1190),
                    "zip_barcode": self._barcode(6.5, 40.0, 720, 170, 285, 765),
                    "text": {
                        "sender": self._text_block(26, 3, 28, 1.3, -8, 1.3),
                        "receiver": self._text_block(105, 235, 40, 1.2, -9, 1.5),
                        "receiver_2nd": self._text_block(105, 310, 60, 1.2, 0, -4),
                        "tracking": self._text_block(293, 1055, 44, 1.1, 0, 0.3),
                        "center_text": {
                            "scale": 2.5,
                            "y_position": 600,
                            "x_position": 115,
                            "width": None,
                            "height": None,
                            "font_size": 50,
                            "line_spacing": 0,
                            "char_spacing": -10,
                            "horizontal_squish": None,
                            "text": None,
                            "whitespace": 0,
                            "x_offset": 0,
                            "y_offset": 0,
                        },
                        "zip_barcode": {"x_position": 285, "y_position": 765},
                        "top_number": {
                            "y_position": -5,
                            "x_position": 617,
                            "width": None,
                            "height": None,
                            "font_size": 52,
                            "scale": 1.0,
                            "line_spacing": 0,
                            "char_spacing": 0,
                            "horizontal_squish": None,
                            "text": "1",
                            "whitespace": 0,
                            "x_offset": 0,
                            "y_offset": 0,
                        },
                    },
                },
                "usps": {
                    "custom_template_path": None,
                    "maxicode": self._maxicode(),
                    "barcode": self._barcode(6.5, 15.0, 760, 205, 115, 1040),
                    "zip_barcode": self._barcode(6.5, 40.0, 720, 170, 285, 765),
                    "text": {
                        "sender": self._text_block(20, 474, 28, 1.0, 7, 1.3),
                        "receiver": self._text_block(165, 725, 40, 1.1, 8, 1.5),
                        "receiver_2nd": self._text_block(165, 825, 40, 1.1, 0, 0),
                        "tracking": self._text_block(262, 1270, 60, 0.6, 0, -1.5),
                    },
                },
                "fedex": {
                    "custom_template_path": None,
                    "maxicode": self._maxicode(),
                    "barcode": self._barcode(6.5, 15.0, 1080, 310, 155, 1588),
                    "zip_barcode": self._barcode(6.5, 40.0, 720, 170, 1120, 1340),
                    "text": {
                        "from_label": self._text_block(70, 14, 34, 1.0, 20, 1, 0.9),
                        "sender": self._text_block(70, 52, 33, 1.0, 20, 1, 0.9),
                        "ship_to_label": self._text_block(70, 262, 34, 1.0, 0, 1, 0.9),
                        "receiver": self._text_block(82, 312, 42, 1.05, 18, 1, 0.9),
                        "tracking": self._text_block(170, 1220, 62, 1.0, 0, 0, 0.9),
                        "tracking_prefix": self._text_block(258, 1480, 55, 0.8, 0, 2.5, 0.91),
                        "receiver_zip": self._text_block(1120, 1340, 60, 1.1, 0, 0, 1.0),
                    },
                },
            },
        }

    def _save_settings(self):
        """Save settings to file atomically so a crash cannot corrupt them."""
        tmp_path = self.settings_file.with_suffix(self.settings_file.suffix + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.settings_file)
        except Exception as e:
            print(f"Warning: Could not save settings: {e}")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get setting value using dot notation."""
        keys = key_path.split(".")
        value = self.settings
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any):
        """Set setting value using dot notation."""
        keys = key_path.split(".")
        current = self.settings
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        self._save_settings()

    def get_from_address(self) -> Dict[str, str]:
        """Get the default From address settings."""
        return self.get("from_address", {})

    def update_from_address(self, zip_code: str = None, city: str = None, state: str = None):
        """Update the default From address settings."""
        if zip_code is not None:
            self.set("from_address.zip_code", zip_code)
        if city is not None:
            self.set("from_address.city", city)
        if state is not None:
            self.set("from_address.state", state)

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.settings = self._get_default_settings()
        self._save_settings()

    def export_settings(self, export_path: str):
        """Export settings to a file."""
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting settings: {e}")
            return False

    def import_settings(self, import_path: str):
        """Import settings from a file."""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                imported = json.load(f)
            defaults = self._get_default_settings()
            self._merge_defaults(imported, defaults)
            self.settings = imported
            self._save_settings()
            return True
        except Exception as e:
            print(f"Error importing settings: {e}")
            return False


_settings_path = Path(os.environ.get("FTID_SETTINGS_FILE", "ftid_settings.json"))
settings = SettingsManager(str(_settings_path))
