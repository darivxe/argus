import random
import string

def generate_investigation_id() -> str:
    """Generate INV-XXXXXX style ID."""
    digits = ''.join(random.choices(string.digits, k=6))
    return f"INV-{digits}"

def generate_id() -> str:
    """Generate short hex ID for all other records."""
    import os
    return os.urandom(8).hex()
