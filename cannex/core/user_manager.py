"""User management functionality for CANNEX application."""
import os
import json
from datetime import datetime
from cannex.config.settings import user_dir, logger

class User:
    """Represents a user of the system"""
    
    def __init__(self, username, fullname="", email="", role="user"):
        self.username = username
        self.fullname = fullname
        self.email = email
        self.role = role  # "admin", "user", "viewer"
        self.last_login = datetime.now().isoformat()
        self.preferences = {}  # User preferences
    
    def to_dict(self):
        """Convert user to dictionary for serialization"""
        return {
            "username": self.username,
            "fullname": self.fullname,
            "email": self.email,
            "role": self.role,
            "last_login": self.last_login,
            "preferences": self.preferences
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create user from dictionary"""
        user = cls(
            username=data["username"],
            fullname=data.get("fullname", ""),
            email=data.get("email", ""),
            role=data.get("role", "user")
        )
        user.last_login = data.get("last_login", datetime.now().isoformat())
        user.preferences = data.get("preferences", {})
        return user
    
    def save(self):
        """Save user data to file"""
        user_file = os.path.join(user_dir, f"{self.username}.json")
        with open(user_file, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)
    
    @classmethod
    def load(cls, username):
        """Load user data from file"""
        user_file = os.path.join(user_dir, f"{username}.json")
        if os.path.exists(user_file):
            with open(user_file, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)
        return None
    
    def update_last_login(self):
        """Update the last login time"""
        self.last_login = datetime.now().isoformat()
        self.save()
    
    def has_permission(self, action):
        """Check if user has permission for an action"""
        if self.role == "admin":
            return True
        
        # Define permissions for different roles
        if self.role == "user":
            # Users can do most things except admin functions
            if action in ["view_instruments", "create_experiment", "run_experiment", 
                         "create_sequence", "export_data"]:
                return True
        
        elif self.role == "viewer":
            # Viewers can only view, not modify
            if action in ["view_instruments", "view_experiment"]:
                return True
        
        return False

class UserManager:
    """Manages system users"""
    
    def __init__(self):
        self.current_user = None
        self.users = {}
        self.load_users()
    
    def load_users(self):
        """Load all users from disk"""
        try:
            self.users = {}
            if os.path.exists(user_dir):
                for file in os.listdir(user_dir):
                    if file.endswith(".json"):
                        username = os.path.splitext(file)[0]
                        self.users[username] = User.load(username)
            
            # Create default admin if no users exist
            if not self.users:
                admin = User("admin", "Administrator", "", "admin")
                self.users["admin"] = admin
                admin.save()
        except Exception as e:
            logger.error(f"Error loading users: {str(e)}")
    
    def login(self, username):
        """Log in a user"""
        if username in self.users:
            self.current_user = self.users[username]
            self.current_user.update_last_login()
            return True
        return False
    
    def logout(self):
        """Log out the current user"""
        self.current_user = None
    
    def add_user(self, username, fullname="", email="", role="user"):
        """Add a new user"""
        if username in self.users:
            return False
        
        user = User(username, fullname, email, role)
        self.users[username] = user
        user.save()
        return True
    
    def delete_user(self, username):
        """Delete a user"""
        if username in self.users:
            user_file = os.path.join(user_dir, f"{username}.json")
            if os.path.exists(user_file):
                os.remove(user_file)
            del self.users[username]
            return True
        return False