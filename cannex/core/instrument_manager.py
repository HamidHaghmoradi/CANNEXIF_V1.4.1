"""Instrument management functionality."""
import os
import inspect
import importlib.util
from PyQt5.QtCore import QDateTime
from PyQt5.QtWidgets import QMessageBox

from cannex.config.settings import logger
from cannex.utils.exceptions import LabVIEWError
from cannex.utils.helpers import get_instrument_name, get_function_name

class InstrumentManager:
    """Manages instrument drivers and functions"""
    
    def __init__(self):
        self.instruments = {}  # Dictionary to store instruments by ID
    
    def load_driver(self, file_path, selected_class_name=None):
        """Load an instrument driver from a Python file"""
        try:
            if not file_path or not os.path.exists(file_path):
                logger.error(f"Driver file not found: {file_path}")
                return None, "Driver file not found"
                
            # Load the Python module
            module_name = os.path.splitext(os.path.basename(file_path))[0]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find classes in the module
            classes = [obj for name, obj in inspect.getmembers(module, inspect.isclass) 
                      if obj.__module__ == module.__name__]
            
            if not classes:
                return None, f"No classes found in {file_path}"
            
            # Select the class to use
            driver_class = None
            if len(classes) == 1:
                driver_class = classes[0]
            elif selected_class_name:
                for cls in classes:
                    if cls.__name__ == selected_class_name:
                        driver_class = cls
                        break
                        
            if not driver_class:
                return classes, "multiple_classes"
            
            # Check for methods
            methods = [m for m, obj in inspect.getmembers(driver_class) 
                     if callable(obj) and not m.startswith("__")]
            
            if not methods:
                return None, f"Driver class '{driver_class.__name__}' has no public callable methods"
            
            # Get suggested name
            suggested_name = get_instrument_name(driver_class)
            
            # Create functions list
            functions = []
            for idx, (method_name, method) in enumerate(inspect.getmembers(driver_class)):
                if (inspect.ismethoddescriptor(method) or inspect.isfunction(method) or 
                    callable(method)) and not method_name.startswith("__"):
                    tag, readable_name = get_function_name(method_name, suggested_name, idx)
                    functions.append((tag, readable_name))
            
            instrument_data = {
                "name": suggested_name,
                "driver_class": driver_class,
                "functions": functions,
                "file_path": file_path
            }
            
            return instrument_data, None
            
        except Exception as e:
            logger.error(f"Error loading driver: {str(e)}")
            return None, f"Error loading driver: {str(e)}"
    
    def execute_function(self, instrument_id, function_name, parameters=None):
        """Execute a function on an instrument"""
        if instrument_id not in self.instruments:
            return LabVIEWError(1000, "InstrumentManager", f"Instrument ID {instrument_id} not found")
            
        instrument = self.instruments[instrument_id]
        
        # Get driver instance
        try:
            driver_instance = instrument["driver_class"]()
        except Exception as e:
            logger.error(f"Failed to instantiate driver for {instrument['name']}: {str(e)}")
            return LabVIEWError(1000, instrument['name'], f"Driver instantiation failed: {str(e)}")
            
        # Run the function
        try:
            method = getattr(driver_instance, function_name)
            params = parameters or {}
            result = method(**params) if params else method()
            
            return result
        except Exception as e:
            error = LabVIEWError(1001, instrument['name'], str(e))
            logger.error(str(error))
            return error
    
    def add_instrument(self, instrument_data, instrument_id=None):
        """Add an instrument to the manager"""
        # Generate ID if not provided
        if instrument_id is None:
            instrument_id = f"inst_{len(self.instruments)}"
        
        self.instruments[instrument_id] = instrument_data
        return instrument_id
    
    def remove_instrument(self, instrument_id):
        """Remove an instrument from the manager"""
        if instrument_id in self.instruments:
            del self.instruments[instrument_id]
            return True
        return False
    
    def get_instrument(self, instrument_id):
        """Get instrument by ID"""
        return self.instruments.get(instrument_id)
    
    def get_all_instruments(self):
        """Get all instruments"""
        return self.instruments