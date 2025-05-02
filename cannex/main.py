"""
Main application entry point for CANNEX Interface.
"""
import sys
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtGui import QFont

# Change these absolute imports to relative imports
from .config.settings import logger, manage_log_files
from .ui.main_window import MainWindow
from .ui.login_dialog import LoginDialog
from .core.user_manager import UserManager


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for consistent look across platforms
    
    # Set application font
    app_font = QFont("Arial", 10)
    app.setFont(app_font)
    
    # Create user manager
    user_manager = UserManager()
    
    # Show login dialog
    login_dialog = LoginDialog(user_manager)
    if login_dialog.exec_() != QDialog.Accepted:
        # User canceled login
        return
    
    # Create and show main window
    main_window = MainWindow(user_manager)
    main_window.show()
    
    # Log application start
    logger.info(f"CANNEX Interface application started - User: {user_manager.current_user.username}")
    
    # Cleanup log files
    manage_log_files()
    
    # Run the application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()