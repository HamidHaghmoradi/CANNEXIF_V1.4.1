"""Base driver class that all instrument drivers should inherit from."""

class BaseDriver:
    """Base class for all instrument drivers"""
    
    def __init__(self):
        """Initialize the driver"""
        self.connected = False
        self.instrument_id = None
    
    def connect(self):
        """Connect to the instrument"""
        self.connected = True
        return True
    
    def disconnect(self):
        """Disconnect from the instrument"""
        self.connected = False
        return True
    
    def is_connected(self):
        """Check if connected to the instrument"""
        return self.connected
    
    def identify(self):
        """Get instrument identification"""
        return "Base Driver - No Identification"
    
    def check_connection(self):
        """Check if instrument is still connected"""
        if not self.connected:
            raise RuntimeError("Not connected to instrument")