# C:/Users/Hamid/Downloads/CANNEXIF_V4.01/run_cannex.py
import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main function from cannex.main
from cannex.main import main

if __name__ == "__main__":
    main()