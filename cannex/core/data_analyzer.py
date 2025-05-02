"""Data analysis functionality for the CANNEX application."""
import numpy as np
import pandas as pd
import logging
from datetime import datetime

from cannex.core.data_logger import DataPoint

logger = logging.getLogger('cannex')

class DataAnalyzer:
    """Analyzes data collected from instruments"""
    
    def __init__(self, data=None):
        self.data = data or []  # List of DataPoint objects
        self.df = None  # pandas DataFrame
    
    def load_data(self, data_points):
        """Load data points for analysis"""
        self.data = data_points
        self.df = self._create_dataframe()
    
    def load_from_file(self, file_path):
        """Load data from a file"""
        try:
            import json
            import h5py
            
            _, ext = os.path.splitext(file_path)
            
            if ext.lower() == '.json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                self.data = [DataPoint.from_dict(dp) for dp in data.get("data_points", [])]
            
            elif ext.lower() == '.csv':
                self.df = pd.read_csv(file_path)
                # Convert back to data points
                self.data = []
                for _, row in self.df.iterrows():
                    self.data.append(DataPoint(
                        instrument_name=row['instrument'],
                        function_name=row['function'],
                        value=row['value'],
                        timestamp=pd.to_datetime(row['timestamp'])
                    ))
            
            elif ext.lower() in ['.xls', '.xlsx']:
                self.df = pd.read_excel(file_path)
                # Convert back to data points
                self.data = []
                for _, row in self.df.iterrows():
                    self.data.append(DataPoint(
                        instrument_name=row['instrument'],
                        function_name=row['function'],
                        value=row['value'],
                        timestamp=pd.to_datetime(row['timestamp'])
                    ))
            
            elif ext.lower() == '.h5':
                with h5py.File(file_path, 'r') as f:
                    # Extract data
                    timestamps = f['data']['timestamp'][:]
                    instruments = f['data']['instrument'][:]
                    functions = f['data']['function'][:]
                    values = f['data']['value'][:]
                    
                    # Convert to data points
                    self.data = []
                    for i in range(len(timestamps)):
                        timestamp = datetime.fromtimestamp(timestamps[i])
                        instrument = instruments[i].decode('utf-8')
                        function = functions[i].decode('utf-8')
                        
                        # Handle value based on type
                        try:
                            value = float(values[i])
                        except:
                            value = values[i].decode('utf-8')
                        
                        self.data.append(DataPoint(
                            instrument_name=instrument,
                            function_name=function,
                            value=value,
                            timestamp=timestamp
                        ))
            
            else:
                logger.error(f"Unsupported file format: {ext}")
                return False
            
            # Create dataframe if not already created
            if self.df is None:
                self.df = self._create_dataframe()
            
            logger.info(f"Loaded {len(self.data)} data points from {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error loading data from file: {str(e)}")
            return False
    
    def _create_dataframe(self):
        """Create a pandas DataFrame from the data points"""
        data = []
        for dp in self.data:
            data.append({
                "instrument": dp.instrument_name,
                "function": dp.function_name,
                "value": dp.value,
                "timestamp": dp.timestamp
            })
        
        df = pd.DataFrame(data)
        
        # Convert timestamp to datetime if it's not already
        if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Try to convert value to numeric if possible
        if 'value' in df.columns:
            df['value'] = pd.to_numeric(df['value'], errors='ignore')
        
        return df
    
    def get_basic_stats(self):
        """Get basic statistics for the data"""
        if self.df is None or len(self.df) == 0:
            return {}
        
        stats = {}
        
        # Group by instrument and function
        for (inst, func), group in self.df.groupby(['instrument', 'function']):
            key = f"{inst} - {func}"
            
            # Check if values are numeric
            if pd.api.types.is_numeric_dtype(group['value']):
                stats[key] = {
                    "count": len(group),
                    "min": group['value'].min(),
                    "max": group['value'].max(),
                    "mean": group['value'].mean(),
                    "median": group['value'].median(),
                    "std": group['value'].std(),
                    "type": "numeric"
                }
            else:
                # Non-numeric data
                value_counts = group['value'].value_counts().to_dict()
                stats[key] = {
                    "count": len(group),
                    "unique_values": len(value_counts),
                    "most_common": group['value'].value_counts().index[0],
                    "most_common_count": group['value'].value_counts().values[0],
                    "type": "categorical"
                }
        
        return stats
    
    def get_time_series(self, instrument, function):
        """Get time series data for a specific instrument and function"""
        if self.df is None or len(self.df) == 0:
            return None
        
        # Filter data
        filtered = self.df[(self.df['instrument'] == instrument) & (self.df['function'] == function)]
        
        if len(filtered) == 0:
            return None
        
        # Sort by timestamp
        filtered = filtered.sort_values('timestamp')
        
        # Return timestamps and values
        return {
            'timestamp': filtered['timestamp'].values,
            'value': filtered['value'].values
        }
    
    def get_correlation(self, instrument1, function1, instrument2, function2):
        """Calculate correlation between two instrument readings"""
        if self.df is None or len(self.df) == 0:
            return None
        
        # Get time series for both
        ts1 = self.get_time_series(instrument1, function1)
        ts2 = self.get_time_series(instrument2, function2)
        
        if ts1 is None or ts2 is None:
            return None
        
        # Check if data is numeric
        if not pd.api.types.is_numeric_dtype(pd.Series(ts1['value'])) or not pd.api.types.is_numeric_dtype(pd.Series(ts2['value'])):
            return None
        
        # Create temporary dataframes
        df1 = pd.DataFrame({'timestamp': ts1['timestamp'], 'value': ts1['value']})
        df2 = pd.DataFrame({'timestamp': ts2['timestamp'], 'value': ts2['value']})
        
        # Merge on closest timestamps
        df1['timestamp_key'] = df1['timestamp']
        df2['timestamp_key'] = df2['timestamp']
        
        # Find matching timestamps or interpolate
        merged = pd.merge_asof(df1.sort_values('timestamp'), 
                              df2.sort_values('timestamp'), 
                              on='timestamp', 
                              direction='nearest',
                              suffixes=('_1', '_2'))
        
        # Calculate correlation
        if len(merged) > 1:
            correlation = merged['value_1'].corr(merged['value_2'])
            return correlation
        
        return None
    
    def detect_anomalies(self, instrument, function, method='zscore', threshold=3.0):
        """Detect anomalies in the data using various methods"""
        if self.df is None or len(self.df) == 0:
            return None
        
        # Get time series
        ts = self.get_time_series(instrument, function)
        if ts is None:
            return None
        
        # Check if data is numeric
        if not pd.api.types.is_numeric_dtype(pd.Series(ts['value'])):
            return None
        
        values = ts['value']
        timestamps = ts['timestamp']
        anomalies = []
        
        if method == 'zscore':
            # Z-score method
            mean = np.mean(values)
            std = np.std(values)
            
            if std == 0:  # Avoid division by zero
                return None
            
            zscores = (values - mean) / std
            
            # Find anomalies
            for i, z in enumerate(zscores):
                if abs(z) > threshold:
                    anomalies.append({
                        'timestamp': timestamps[i],
                        'value': values[i],
                        'zscore': z
                    })
        
        elif method == 'iqr':
            # IQR method
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr
            
            # Find anomalies
            for i, val in enumerate(values):
                if val < lower_bound or val > upper_bound:
                    anomalies.append({
                        'timestamp': timestamps[i],
                        'value': val,
                        'bound': lower_bound if val < lower_bound else upper_bound
                    })
        
        return anomalies
    
    def get_trend(self, instrument, function, window=5):
        """Calculate trend (moving average) for a time series"""
        if self.df is None or len(self.df) == 0:
            return None
        
        # Get time series
        ts = self.get_time_series(instrument, function)
        if ts is None or len(ts['value']) < window:
            return None
        
        # Check if data is numeric
        if not pd.api.types.is_numeric_dtype(pd.Series(ts['value'])):
            return None
        
        # Calculate moving average
        values = ts['value']
        timestamps = ts['timestamp']
        
        moving_avg = []
        for i in range(len(values)):
            if i < window - 1:
                # Not enough data points yet
                moving_avg.append(None)
            else:
                # Calculate average of window
                window_avg = np.mean(values[i-(window-1):i+1])
                moving_avg.append(window_avg)
        
        return {
            'timestamp': timestamps,
            'value': values,
            'trend': moving_avg
        }
    
    def forecast_values(self, instrument, function, periods=10):
        """Simple forecasting using linear regression"""
        try:
            from sklearn.linear_model import LinearRegression
            
            # Get time series
            ts = self.get_time_series(instrument, function)
            if ts is None or len(ts['value']) < 5:  # Need at least 5 points
                return None
            
            # Check if data is numeric
            if not pd.api.types.is_numeric_dtype(pd.Series(ts['value'])):
                return None
            
            # Convert timestamps to numeric index
            time_index = np.arange(len(ts['timestamp']))
            values = ts['value']
            
            # Create and fit model
            model = LinearRegression()
            model.fit(time_index.reshape(-1, 1), values)
            
            # Generate forecast
            forecast_index = np.arange(len(time_index), len(time_index) + periods)
            forecast = model.predict(forecast_index.reshape(-1, 1))
            
            # Generate forecast timestamps
            last_timestamp = ts['timestamp'][-1]
            timestamp_diff = np.median(np.diff(ts['timestamp']))  # Median time difference
            
            forecast_timestamps = []
            for i in range(1, periods + 1):
                if isinstance(last_timestamp, np.datetime64):
                    forecast_timestamps.append(last_timestamp + np.timedelta64(int(i * timestamp_diff), 's'))
                else:
                    forecast_timestamps.append(last_timestamp + i * timestamp_diff)
            
            return {
                'timestamp': forecast_timestamps,
                'forecast': forecast,
                'historical_timestamps': ts['timestamp'],
                'historical_values': ts['value']
            }
        
        except Exception as e:
            logger.error(f"Error forecasting values: {str(e)}")
            return None