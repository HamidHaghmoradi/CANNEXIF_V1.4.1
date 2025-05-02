"""Data logging functionality for the CANNEX application."""
import os
import json
import time
import csv
import h5py
import pandas as pd
import numpy as np
from datetime import datetime
from PyQt5.QtCore import QTimer

from cannex.config.settings import data_dir, logger
from cannex.config.constants import APP_AUTHOR, APP_VERSION

class DataPoint:
    """Represents a single data point from an instrument"""
    
    def __init__(self, instrument_name, function_name, value, timestamp=None):
        self.instrument_name = instrument_name
        self.function_name = function_name
        self.value = value
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "instrument": self.instrument_name,
            "function": self.function_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary"""
        return cls(
            instrument_name=data["instrument"],
            function_name=data["function"],
            value=data["value"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )

class DataLogger:
    """Data logger for recording instrument outputs"""
    
    def __init__(self, experiment_name=None):
        self.experiment_name = experiment_name
        self.session_name = f"session_{int(time.time())}"
        self.data_points = []
        self.is_logging = False
        self.log_interval = 1000  # ms
        self.log_timer = None
        self.instruments = []
        self.auto_save = False
        self.auto_save_interval = 60000  # 1 minute
        self.auto_save_timer = None
        self.metadata = {
            "created_by": APP_AUTHOR,
            "app_version": APP_VERSION,
            "creation_date": datetime.now().isoformat()
        }
    
    def start_logging(self, instruments):
        """Start logging data from instruments"""
        if self.is_logging:
            return
        
        self.instruments = instruments
        self.is_logging = True
        
        # Create and start the log timer
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.log_data)
        self.log_timer.start(self.log_interval)
        
        # Setup auto-save if enabled
        if self.auto_save:
            self.auto_save_timer = QTimer()
            self.auto_save_timer.timeout.connect(self.save_data)
            self.auto_save_timer.start(self.auto_save_interval)
        
        logger.info(f"Started data logging session '{self.session_name}' "
                  f"with {len(instruments)} instruments")
    
    def stop_logging(self):
        """Stop logging data"""
        if not self.is_logging:
            return
        
        self.is_logging = False
        
        if self.log_timer:
            self.log_timer.stop()
            self.log_timer = None
        
        if self.auto_save_timer:
            self.auto_save_timer.stop()
            self.auto_save_timer = None
        
        logger.info(f"Stopped data logging session '{self.session_name}' "
                  f"with {len(self.data_points)} data points")
    
    def log_data(self):
        """Log data from all instruments"""
        if not self.is_logging:
            return
        
        current_time = datetime.now()
        
        for instrument in self.instruments:
            if not instrument.selected_function:
                continue
            
            try:
                # Get value from instrument
                result = instrument.run_function()
                
                # Create data point
                data_point = DataPoint(
                    instrument_name=instrument.instrument_data["name"],
                    function_name=instrument.selected_function,
                    value=result,
                    timestamp=current_time
                )
                
                # Add to data points
                self.data_points.append(data_point)
            except Exception as e:
                logger.error(f"Error logging data from {instrument.instrument_data['name']}: {str(e)}")
    
    def set_metadata(self, key, value):
        """Set metadata value"""
        self.metadata[key] = value
    
    def get_metadata(self, key, default=None):
        """Get metadata value"""
        return self.metadata.get(key, default)
    
    def add_data_point(self, data_point):
        """Add a data point manually"""
        self.data_points.append(data_point)
    
    def clear_data(self):
        """Clear all data points"""
        self.data_points = []
    
    def get_data_frame(self):
        """Get data as a pandas DataFrame"""
        data = []
        for dp in self.data_points:
            data.append({
                "instrument": dp.instrument_name,
                "function": dp.function_name,
                "value": dp.value,
                "timestamp": dp.timestamp
            })
        
        return pd.DataFrame(data)
    
    def save_data(self, file_path=None):
        """Save data to file"""
        if not file_path:
            # Generate default file path
            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{self.session_name}_{time_str}.json"
            file_path = os.path.join(data_dir, file_name)
        
        data = {
            "session_name": self.session_name,
            "experiment_name": self.experiment_name,
            "metadata": self.metadata,
            "data_points": [dp.to_dict() for dp in self.data_points]
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        logger.info(f"Saved {len(self.data_points)} data points to {file_path}")
        return file_path
    
    def load_data(self, file_path):
        """Load data from file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        self.session_name = data.get("session_name", os.path.basename(file_path))
        self.experiment_name = data.get("experiment_name")
        self.metadata = data.get("metadata", {})
        
        self.data_points = []
        for dp_data in data.get("data_points", []):
            self.data_points.append(DataPoint.from_dict(dp_data))
        
        logger.info(f"Loaded {len(self.data_points)} data points from {file_path}")
    
    def export_csv(self, file_path):
        """Export data to CSV file"""
        df = self.get_data_frame()
        df.to_csv(file_path, index=False)
        logger.info(f"Exported data to CSV: {file_path}")
    
    def export_excel(self, file_path):
        """Export data to Excel file"""
        df = self.get_data_frame()
        df.to_excel(file_path, index=False)
        logger.info(f"Exported data to Excel: {file_path}")
    
    def export_hdf5(self, file_path):
        """Export data to HDF5 file"""
        df = self.get_data_frame()
        
        with h5py.File(file_path, 'w') as f:
            # Create metadata group
            meta = f.create_group('metadata')
            for key, value in self.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    meta.attrs[key] = value
            
            # Add session info
            meta.attrs['session_name'] = self.session_name
            if self.experiment_name:
                meta.attrs['experiment_name'] = self.experiment_name
            
            # Create datasets for each column
            data_group = f.create_group('data')
            
            # Convert timestamps to numeric values
            timestamps = np.array([pd.Timestamp(t).timestamp() for t in df['timestamp']])
            data_group.create_dataset('timestamp', data=timestamps)
            
            instruments = df['instrument'].values
            data_group.create_dataset('instrument', data=np.array([str(i).encode('utf-8') for i in instruments]))
            
            functions = df['function'].values
            data_group.create_dataset('function', data=np.array([str(f).encode('utf-8') for f in functions]))
            
            # Try to convert values to numeric if possible
            try:
                values = df['value'].values.astype(float)
            except:
                values = np.array([str(v).encode('utf-8') for v in df['value'].values])
            
            data_group.create_dataset('value', data=values)
        
        logger.info(f"Exported data to HDF5: {file_path}")
    
    def get_statistics(self):
        """Get basic statistics on the data"""
        try:
            df = self.get_data_frame()
            
            # Group by instrument and function
            stats = {}
            for (inst, func), group in df.groupby(['instrument', 'function']):
                # Try to calculate numeric statistics
                try:
                    values = pd.to_numeric(group['value'])
                    stats[f"{inst} - {func}"] = {
                        "count": len(values),
                        "min": values.min(),
                        "max": values.max(),
                        "mean": values.mean(),
                        "median": values.median(),
                        "std": values.std()
                    }
                except:
                    # Non-numeric data
                    stats[f"{inst} - {func}"] = {
                        "count": len(group),
                        "data_type": "non-numeric"
                    }
            
            return stats
        except Exception as e:
            logger.error(f"Error calculating statistics: {str(e)}")
            return {}