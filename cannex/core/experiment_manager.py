"""Experiment management functionality."""
import os
import json
from datetime import datetime
from PyQt5.QtCore import QDateTime

from cannex.config.settings import experiment_dir, logger

class ExperimentManager:
    """Manages experiments - creation, loading, saving"""
    
    def __init__(self):
        self.experiments = {}  # Dictionary of experiment names to data
        self.load_experiments()
    
    def load_experiments(self):
        """Load all experiments from disk"""
        try:
            os.makedirs(experiment_dir, exist_ok=True)
            
            # Clear existing experiments
            self.experiments = {}
            
            # Load each experiment file
            for file_name in os.listdir(experiment_dir):
                if file_name.endswith('.json'):
                    try:
                        exp_name = os.path.splitext(file_name)[0]
                        self.experiments[exp_name] = {
                            "window": None,
                            "active": False,
                            "created_by": "Unknown",  # Default if not found in file
                            "creation_date": datetime.now().isoformat()  # Default if not found in file
                        }
                        
                        # Try to get metadata from file
                        file_path = os.path.join(experiment_dir, file_name)
                        try:
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                                if "created_by" in data:
                                    self.experiments[exp_name]["created_by"] = data["created_by"]
                                if "creation_date" in data:
                                    self.experiments[exp_name]["creation_date"] = data["creation_date"]
                        except:
                            pass  # Use defaults if can't read file
                    except Exception as e:
                        logger.error(f"Error loading experiment {file_name}: {str(e)}")
            
            logger.info(f"Loaded {len(self.experiments)} experiments")
            return self.experiments
        
        except Exception as e:
            logger.error(f"Error loading experiments: {str(e)}")
            return {}
    
    def create_experiment(self, name, creator):
        """Create a new experiment"""
        if name in self.experiments:
            return False, "An experiment with this name already exists"
        
        # Create experiment entry
        self.experiments[name] = {
            "window": None,
            "active": False,
            "created_by": creator,
            "creation_date": datetime.now().isoformat()
        }
        
        logger.info(f"Created new experiment '{name}' by {creator}")
        return True, name
    
    def save_experiment(self, name, data):
        """Save experiment data to disk"""
        try:
            os.makedirs(experiment_dir, exist_ok=True)
            
            file_path = os.path.join(experiment_dir, f"{name}.json")
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved experiment '{name}'")
            return True, file_path
        except Exception as e:
            logger.error(f"Failed to save experiment '{name}': {str(e)}")
            return False, str(e)
    
    def load_experiment_data(self, name):
        """Load experiment data from disk"""
        try:
            file_path = os.path.join(experiment_dir, f"{name}.json")
            
            if not os.path.exists(file_path):
                return False, f"Experiment file for '{name}' not found"
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            logger.info(f"Loaded data for experiment '{name}'")
            return True, data
        except Exception as e:
            logger.error(f"Failed to load experiment data for '{name}': {str(e)}")
            return False, str(e)
    
    def delete_experiment(self, name):
        """Delete an experiment"""
        try:
            # Check if experiment exists
            if name not in self.experiments:
                return False, f"Experiment '{name}' not found"
            
            # Check if window is open
            if self.experiments[name]["window"] is not None:
                return False, "Cannot delete an open experiment. Please close it first."
            
            # Delete file
            file_path = os.path.join(experiment_dir, f"{name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Remove from dictionary
            del self.experiments[name]
            
            logger.info(f"Deleted experiment '{name}'")
            return True, name
        except Exception as e:
            logger.error(f"Failed to delete experiment '{name}': {str(e)}")
            return False, str(e)
    
    def update_experiment_status(self, name, active):
        """Update the active status of an experiment"""
        if name in self.experiments:
            self.experiments[name]["active"] = active
            return True
        return False
    
    def set_experiment_window(self, name, window):
        """Associate a window with an experiment"""
        if name in self.experiments:
            self.experiments[name]["window"] = window
            return True
        return False
    
    def import_experiment(self, template_path, new_name, creator):
        """Import an experiment from a template file"""
        try:
            # Check if name already exists
            if new_name in self.experiments:
                return False, "An experiment with this name already exists"
            
            # Load template data
            with open(template_path, 'r') as f:
                template_data = json.load(f)
            
            # Create experiment entry
            self.experiments[new_name] = {
                "window": None,
                "active": False,
                "created_by": creator,
                "creation_date": datetime.now().isoformat(),
                "imported_from": os.path.basename(template_path)
            }
            
            # Save the imported experiment
            self.save_experiment(new_name, template_data)
            
            logger.info(f"Imported experiment '{new_name}' from template '{template_path}'")
            return True, template_data
        except Exception as e:
            logger.error(f"Failed to import template: {str(e)}")
            return False, str(e)