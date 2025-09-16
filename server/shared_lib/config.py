# Import from main shared_lib
from shared_lib.config import *

# Legacy compatibility
from shared_lib.config import get_config

def get_settings():
    """Legacy compatibility function."""
    return get_config()

settings = get_settings()
