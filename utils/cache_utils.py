"""
Persistent caching utilities for contact info and ATS scores.
Saves to disk to persist across sessions and avoid re-analysis.
"""

import os
import pickle
from typing import Dict, Any
from config import CONTACT_CACHE, ATS_CACHE


def load_contact_cache() -> Dict:
    """Load contact info cache from disk."""
    if os.path.exists(CONTACT_CACHE):
        try:
            with open(CONTACT_CACHE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def save_contact_cache(cache: Dict):
    """Save contact info cache to disk."""
    try:
        with open(CONTACT_CACHE, "wb") as f:
            pickle.dump(cache, f)
    except Exception as e:
        print(f"Warning: Could not save contact cache: {e}")


def load_ats_cache() -> Dict:
    """Load ATS scores cache from disk."""
    if os.path.exists(ATS_CACHE):
        try:
            with open(ATS_CACHE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def save_ats_cache(cache: Dict):
    """Save ATS scores cache to disk."""
    try:
        with open(ATS_CACHE, "wb") as f:
            pickle.dump(cache, f)
    except Exception as e:
        print(f"Warning: Could not save ATS cache: {e}")


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about cached data."""
    contact_cache = load_contact_cache()
    ats_cache = load_ats_cache()
    
    return {
        "contact_entries": len(contact_cache),
        "ats_entries": len(ats_cache),
        "contact_cache_size_kb": os.path.getsize(CONTACT_CACHE) / 1024 if os.path.exists(CONTACT_CACHE) else 0,
        "ats_cache_size_kb": os.path.getsize(ATS_CACHE) / 1024 if os.path.exists(ATS_CACHE) else 0
    }
