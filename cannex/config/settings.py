"""Settings configuration for the CANNEX application."""
import os
import logging
import time
from datetime import datetime

# Get the script directory
script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up directory paths
log_dir = os.path.join(script_dir, 'logs')
data_dir = os.path.join(script_dir, 'data')
experiment_dir = os.path.join(script_dir, 'experiments')
sequence_dir = os.path.join(script_dir, 'sequences')
template_dir = os.path.join(script_dir, 'templates')
user_dir = os.path.join(script_dir, 'users')

# Create directories
for directory in [log_dir, data_dir, experiment_dir, sequence_dir, template_dir, user_dir]:
    os.makedirs(directory, exist_ok=True)

# Generate timestamped log file name
timestamp = time.strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f'cannex_{timestamp}.txt')

# Configure logger
logger = logging.getLogger('cannex')
logger.setLevel(logging.DEBUG)

# File handler
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Reset and add handlers
logger.handlers = []
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def manage_log_files():
    """Manage log files to keep the latest 5"""
    from glob import glob
    log_files = sorted(glob(os.path.join(log_dir, 'cannex_*.txt')))
    while len(log_files) > 5:  # Keep the latest 5 logs
        try:
            os.remove(log_files.pop(0))  # Delete the oldest
            logger.debug(f"Deleted old log file: {log_files[0]}")
        except Exception as e:
            logger.error(f"Failed to delete old log file: {str(e)}")