"""
Liquipedia API client for fetching Dota 2 match schedules.
Free community wrapper at dota.haglund.dev (no auth required).
"""
import requests
from typing import Optional, List, Dict

BASE_URL = "https://dota.haglund.dev/v1"

def get_upcoming_matches(limit: Optional[int] = None) -> List[Dict]:
    """
    Fetch upcoming Dota 2 matches from Liquipedia API.
    
    Returns:
        List of match dicts with structure:
        {
            'id': str,
            'teams': [{'name': str, 'url': str}, ...],
            'matchType': str,  # e.g. 'Bo3'
            'startsAt': str,   # ISO timestamp
            'leagueName': str,
            'streamUrl': str | None
        }
    """
    resp = requests.get(f"{BASE_URL}/matches", timeout=10)
    resp.raise_for_status()
    matches = resp.json()
    
    if limit:
        return matches[:limit]
    return matches
