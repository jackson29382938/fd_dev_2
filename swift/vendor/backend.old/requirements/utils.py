import sys
import os

def resource_path(relative_path):
    """Get absolute path to resource inside .app or normal environment."""
    try:
        base_path = sys._MEIPASS  # For PyInstaller (if used)
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
