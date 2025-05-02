"""Helper functions for the CANNEX application."""

def get_instrument_name(driver_class):
    """Extract a readable name from a driver class"""
    name = driver_class.__name__.replace("Driver", "").replace("Instrument", "")
    return name if name else "UnknownInstrument"

def get_function_name(func_name, instrument_name, index):
    """Generate a tag and readable name for an instrument function"""
    func_name = func_name.replace("_", " ").title()
    base_initials = {
        "read": "RE", "set on": "ON", "set off": "OF", "set": "SE", "enable": "EN",
        "disable": "DI", "dump": "DU", "store": "ST", "download": "ST", "start": "SA", "stop": "SP"
    }
    for key, initial in base_initials.items():
        if key in func_name.lower():
            return f"{initial}{index if index > 0 else ''}", f"{instrument_name} - {func_name}"
    return f"F{index}", f"{instrument_name} - {func_name}"