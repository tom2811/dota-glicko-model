"""
PandaScore API utility for fetching Dota 2 match data.
Handles rate limiting and API authentication.
"""
import os
import requests
import time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PANDASCORE_API_KEY")
BASE_URL = os.getenv("PANDASCORE_BASE_URL", "https://api.pandascore.co")

# Rate limit: ~1000 req/hr = ~16/min, be conservative
_last_request_time = 0
_min_request_interval = 1  # 60 req/min for batch operations, still under 1000/hr limit

def _rate_limit():
    """Simple rate limiting: wait if needed."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _min_request_interval:
        time.sleep(_min_request_interval - elapsed)
    _last_request_time = time.time()

def _get(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make authenticated GET request with rate limiting."""
    _rate_limit()
    url = f"{BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    resp = requests.get(url, headers=headers, params=params or {}, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_upcoming_matches(per_page: int = 20) -> list[dict]:
    """
    Fetch upcoming Dota 2 matches.
    Returns list of match objects with opponents, scheduled_at, league info.
    """
    return _get("dota2/matches/upcoming", {"per_page": per_page})

def get_running_matches() -> list[dict]:
    """
    Fetch currently running Dota 2 matches.
    Returns list of live match objects.
    """
    return _get("dota2/matches/running")

def get_team_roster(team_id: int) -> list[dict]:
    """
    Fetch current roster for a team.
    Returns list of player objects with id, name, etc.
    Returns empty list if team not found.
    """
    try:
        team = _get(f"dota2/teams/{team_id}")
        return team.get("players", [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return []
        raise

def get_all_teams(page: int = 1, per_page: int = 25) -> list[dict]:
    """
    Fetch Dota 2 teams (for building player mapping).
    Returns list of team objects.
    """
    return _get("dota2/teams", {"page": page, "per_page": per_page})
