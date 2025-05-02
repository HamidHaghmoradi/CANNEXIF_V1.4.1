"""Registry for instrument drivers."""
import os
import importlib.util
import inspect
from cannex.config.settings import logger
from cannex.drivers.base_driver import BaseDriver

class DriverRegistry:
    """Registry of available instrument drivers"""
    
    def __init__(self):
        self.drivers = {}  # Dictionary of available drivers
    
    def scan_directory(self, directory):
        """Scan a directory for driver modules"""
        driver_count = 0
        
        if not os.path.exists(directory):
            logger.warning(f"Driver directory not found: {directory}")
            return driver_count
        
        # Look for Python files in the directory
        for filename in os.listdir(directory):
            if filename.endswith('.py') and filename != '__init__.py':
                module_path = os.path.join(directory, filename)
                try:
                    # Load the module
                    module_name = os.path.splitext(filename)[0]
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find driver classes (classes that inherit from BaseDriver)
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            obj.__module__ == module.__name__ and 
                            issubclass(obj, BaseDriver) and 
                            obj != BaseDriver):
                            
                            # Add to registry
                            driver_id = f"{module_name}.{name}"
                            self.drivers[driver_id] = {
                                'class': obj,
                                'module': module,
                                'path': module_path,
                                'name': name
                            }
                            driver_count += 1
                            logger.debug(f"Registered driver: {driver_id}")
                
                except Exception as e:
                    logger.error(f"Error loading driver module {filename}: {str(e)}")
        
        return driver_count
    
    def get_driver(self, driver_id):
        """Get a driver class by ID"""
        if driver_id in self.drivers:
            return self.drivers[driver_id]['class']
        return None
    
    def list_drivers(self):
        """List all available drivers"""
        return list(self.drivers.keys())
    
    def get_driver_info(self, driver_id):
        """Get information about a driver"""
        if driver_id in self.drivers:
            return self.drivers[driver_id]
        return None