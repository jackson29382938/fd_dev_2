"""
FTID Generator Logging Configuration
Centralized logging setup for the application.
"""
import logging
import os
import sys
from datetime import datetime
from ftid_gen.config import DEBUG

# Default log directory
LOG_DIR = os.path.join(os.getcwd(), "logs")

def setup_logging(name: str = "ftid_generator") -> logging.Logger:
    """
    Set up and return a configured logger.
    
    In DEBUG mode: Shows INFO+ to console, DEBUG+ to file
    In Production: Shows WARNING+ to console, INFO+ to file
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Create formatters
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if DEBUG:
        console_handler.setLevel(logging.INFO)
    else:
        console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler (only if not frozen/bundled, or if logs dir exists)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_filename = f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(os.path.join(LOG_DIR, log_filename))
        file_handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except (PermissionError, OSError):
        # Can't write logs (e.g., in bundled app without write permissions)
        pass
    
    return logger


# Create default logger
logger = setup_logging()
