"""Login dialog for the CANNEX application."""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QComboBox, QCheckBox, QLineEdit, QPushButton,
                            QMessageBox, QFormLayout)
from PyQt5.QtCore import Qt

class LoginDialog(QDialog):
    """Dialog for user login"""
    
    def __init__(self, user_manager, parent=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.setWindowTitle("Login - CANNEX Interface")
        self.setFixedSize(400, 250)
        
        layout = QVBoxLayout(self)
        
        # Logo or title
        title_label = QLabel("CANNEX Interface")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        layout.addWidget(title_label)
        
        # Username
        username_layout = QHBoxLayout()
        username_layout.addWidget(QLabel("Username:"))
        self.username_edit = QComboBox()
        self.username_edit.setEditable(True)
        
        # Populate with existing users
        for username in user_manager.users.keys():
            self.username_edit.addItem(username)
        
        username_layout.addWidget(self.username_edit)
        layout.addLayout(username_layout)
        
        # Quick access buttons for admin and guest
        quick_layout = QHBoxLayout()
        
        admin_btn = QPushButton("Admin")
        admin_btn.clicked.connect(lambda: self.username_edit.setCurrentText("admin"))
        quick_layout.addWidget(admin_btn)
        
        guest_btn = QPushButton("Guest")
        guest_btn.clicked.connect(lambda: self.username_edit.setCurrentText("guest"))
        quick_layout.addWidget(guest_btn)
        
        layout.addLayout(quick_layout)
        
        # Create new user checkbox
        self.new_user_check = QCheckBox("Create new user")
        layout.addWidget(self.new_user_check)
        
        # New user details - initially hidden
        self.new_user_widget = QWidget()
        new_user_layout = QFormLayout(self.new_user_widget)
        
        self.fullname_edit = QLineEdit()
        new_user_layout.addRow("Full Name:", self.fullname_edit)
        
        self.email_edit = QLineEdit()
        new_user_layout.addRow("Email:", self.email_edit)
        
        self.role_combo = QComboBox()
        self.role_combo.addItems(["user", "viewer"])
        new_user_layout.addRow("Role:", self.role_combo)
        
        self.new_user_widget.setVisible(False)
        layout.addWidget(self.new_user_widget)
        
        # Connect checkbox to toggle new user fields
        self.new_user_check.toggled.connect(self.new_user_widget.setVisible)
        
        # Login button
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self.accept)
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(login_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Exit")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
    
    def accept(self):
        """Handle login button press"""
        username = self.username_edit.currentText().strip()
        
        if not username:
            QMessageBox.warning(self, "Login Error", "Please enter a username.")
            return
        
        if self.new_user_check.isChecked():
            # Create new user
            fullname = self.fullname_edit.text().strip()
            email = self.email_edit.text().strip()
            role = self.role_combo.currentText()
            
            if self.user_manager.add_user(username, fullname, email, role):
                self.user_manager.login(username)
                super().accept()
            else:
                QMessageBox.warning(self, "Create User Error", 
                                  f"User '{username}' already exists. Please choose another username.")
        else:
            # Login existing user
            if username not in self.user_manager.users:
                # Create user on-the-fly
                if username == "guest":
                    self.user_manager.add_user("guest", "Guest User", "", "viewer")
                elif username == "admin" and not self.user_manager.users:
                    # Create admin if no users exist
                    self.user_manager.add_user("admin", "Administrator", "", "admin")
            
            if self.user_manager.login(username):
                super().accept()
            else:
                QMessageBox.warning(self, "Login Error", 
                                  f"User '{username}' not found.")