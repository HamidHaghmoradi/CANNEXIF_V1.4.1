"""Custom exceptions for the CANNEX application."""

class LabVIEWError:
    """Class to represent errors similar to LabVIEW errors"""
    def __init__(self, code, source, description):
        self.code = code
        self.source = source
        self.description = description

    def __str__(self):
        return f"Error {self.code} at {self.source}: {self.description}"