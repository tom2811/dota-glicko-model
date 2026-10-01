"""
OpenDota API client for fetching team rosters.
Uses the same data source as our training pipeline (no auth required).
"""
import requests
import json
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta

BASE_URL = "https://api.opendota.com/api"
CACHE_FILE = None
_team_roster_cache = {}
CACHE_TTL_DAYS = 7

def _get_cache_path():
    """Get path to roster cache file."""
    global CACHE_FILE
    if CACHE_FILE is None:
        CACHE_FILE = os.path.join(
            os.path.dirname(__file__), "..", "data", "opendota_rosters.json"
        )
    return CACHE_FILE

def _load_cache():
    """Load cached rosters from disk."""
    global _team_roster_cache
    if _team_roster_cache:
        return
    
    cache_path = _get_cache_path()
    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            _team_roster_cache = json.load(f)
    else:
        _team_roster_cache = {}

def _save_cache():
    """Save roster cache to disk."""
    cache_path = _get_cache_path()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(_team_roster_cache, f, indent=2)

def get_all_teams(min_rating: int = 1400) -> List[Dict]:
    """
    Get all professional teams from OpenDota.
    
    Args:
        min_rating: Minimum team rating (default 1400 filters tier 2+)
    
    Returns:
        List of team dicts with team_id, name, tag, rating
    """
    try:
        resp = requests.get(f"{BASE_URL}/teams", timeout=10)
        resp.raise_for_status()
        teams = resp.json()
        
        # Filter by rating and recent activity
        active_teams = [
            t for t in teams 
            if t.get("rating", 0) >= min_rating and t.get("last_match_time", 0) > 0
        ]
        
        return active_teams
    except Exception as e:
        print(f"Failed to fetch teams: {e}")
        return []

def get_team_roster_by_id(team_id: int) -> List[Dict]:
    """
    Get current roster for a team by OpenDota team_id.
    
    Args:
        team_id: OpenDota team ID (numeric)
    
    Returns:
        List of player dicts: [{'name': str, 'account_id': int, 'position': None}, ...]
        Only returns current team members.
    """
    _load_cache()
    
    # Check cache
    cache_key = str(team_id)
    if cache_key in _team_roster_cache:
        cached = _team_roster_cache[cache_key]
        cached_at = datetime.fromisoformat(cached["cached_at"])
        if datetime.now() - cached_at < timedelta(days=CACHE_TTL_DAYS):
            return cached["players"]
    
    # Fetch from API
    try:
        resp = requests.get(f"{BASE_URL}/teams/{team_id}/players", timeout=10)
        resp.raise_for_status()
        all_players = resp.json()
        
        # Filter to current members, fallback to top 5 if none marked current
        current_roster = [
            {
                "name": p.get("name") or f"Player_{p['account_id']}",
                "account_id": p["account_id"],
                "position": None,  # OpenDota doesn't provide position
                "games_played": p.get("games_played", 0)
            }
            for p in all_players
            if p.get("is_current_team_member") is True
        ]
        
        # If no current members marked, take top 5 by games played
        if len(current_roster) < 5:
            all_active = [
                {
                    "name": p.get("name") or f"Player_{p['account_id']}",
                    "account_id": p["account_id"],
                    "position": None,
                    "games_played": p.get("games_played", 0)
                }
                for p in all_players
                if p.get("name") and p.get("games_played", 0) > 10  # At least 10 games
            ]
            all_active.sort(key=lambda p: p["games_played"], reverse=True)
            current_roster = all_active[:5]
        
        # Remove games_played from output
        for p in current_roster:
            del p["games_played"]
        
        # Only cache if we have at least 3 players
        if len(current_roster) >= 3:
            _team_roster_cache[cache_key] = {
                "players": current_roster,
                "cached_at": datetime.now().isoformat()
            }
            _save_cache()
        
        return current_roster
    
    except Exception as e:
        print(f"Failed to fetch roster for team {team_id}: {e}")
        return []

def get_team_roster_by_name(team_name: str) -> List[Dict]:
    """
    Get roster by team name (matches against OpenDota team names).
    
    Args:
        team_name: Team name from Liquipedia (e.g., "Team Spirit")
    
    Returns:
        List of player dicts with name and account_id
    """
    teams = get_all_teams(min_rating=1300)
    
    # Normalize for matching
    def normalize(name):
        return name.lower().replace("team ", "").replace(" esports", "").replace(" gaming", "").strip()
    
    norm_search = normalize(team_name)
    
    # Exact match first
    for team in teams:
        if team.get("name", "").lower() == team_name.lower():
            return get_team_roster_by_id(team["team_id"])
    
    # Normalized exact match
    for team in teams:
        if normalize(team.get("name", "")) == norm_search:
            return get_team_roster_by_id(team["team_id"])
    
    # Fuzzy match (contains)
    for team in teams:
        team_norm = normalize(team.get("name", ""))
        if norm_search in team_norm or team_norm in norm_search:
            return get_team_roster_by_id(team["team_id"])
    
    # Last resort: check tag/acronym
    for team in teams:
        tag = team.get("tag", "").lower()
        if tag and tag == norm_search:
            return get_team_roster_by_id(team["team_id"])
    
    return []

def build_roster_cache_for_top_teams(limit: int = 50):
    """
    Pre-fetch and cache rosters for top N teams.
    Useful to run at startup or periodically.
    """
    print(f"Fetching rosters for top {limit} teams...")
    teams = get_all_teams()
    teams.sort(key=lambda t: t.get("rating", 0), reverse=True)
    
    for team in teams[:limit]:
        roster = get_team_roster_by_id(team["team_id"])
        if roster:
            print(f"  ✓ {team['name']}: {len(roster)} players")
        else:
            print(f"  ✗ {team['name']}: No roster found")
    
    print(f"\nCached {len(_team_roster_cache)} team rosters")
    _save_cache()

if __name__ == "__main__":
    # Test and build cache
    build_roster_cache_for_top_teams(50)
