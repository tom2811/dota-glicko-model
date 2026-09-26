"""
Liquipedia web scraper for extracting team rosters.
Caches results for 7 days to minimize requests.
"""
import os
import json
import time
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://liquipedia.net/dota2"
USER_AGENT = "DotaGlickoPredictor/1.0 (Educational Project; github.com/yourusername/dota-glicko-model)"
RATE_LIMIT_SECONDS = 2  # Be respectful
CACHE_TTL_DAYS = 7

_cache_file = None
_roster_cache = {}
_last_request_time = 0

def _get_cache_path():
    """Get absolute path to roster cache file."""
    global _cache_file
    if _cache_file is None:
        _cache_file = os.path.join(
            os.path.dirname(__file__), "..", "data", "team_rosters.json"
        )
    return _cache_file

def _load_cache():
    """Load roster cache from disk."""
    global _roster_cache
    if _roster_cache:
        return
    
    cache_path = _get_cache_path()
    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            _roster_cache = json.load(f)
    else:
        _roster_cache = {}

def _save_cache():
    """Persist roster cache to disk."""
    cache_path = _get_cache_path()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(_roster_cache, f, indent=2)

def _rate_limit():
    """Enforce rate limiting between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    _last_request_time = time.time()

def _normalize_team_name(team_name: str) -> str:
    """Convert team name to Liquipedia URL format."""
    # Replace spaces with underscores, handle special chars
    normalized = team_name.replace(" ", "_")
    # Remove or escape problematic characters
    normalized = re.sub(r'[^\w\-_]', '', normalized)
    return normalized

def _parse_roster(html: str) -> List[Dict]:
    """
    Parse team roster from Liquipedia HTML.
    Looks for the active roster table and extracts player names + positions.
    """
    soup = BeautifulSoup(html, 'lxml')
    
    # Find roster table (typically has class 'roster-card' or similar)
    # Look for tables with "Active Squad" or "Roster" headers
    roster_players = []
    
    # Strategy: Find divs with class 'teamcard-toggle-players'
    player_divs = soup.find_all('div', class_='teamcard-toggle-players')
    if not player_divs:
        # Fallback: look for any table with "ID" column (common roster format)
        tables = soup.find_all('table', class_='wikitable')
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            if 'id' in headers and 'name' in headers:
                player_divs = [table]
                break
    
    if not player_divs:
        return []
    
    # Parse player rows
    for container in player_divs[:1]:  # Only first active roster
        rows = container.find_all('tr')
        for row in rows[1:]:  # Skip header
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                # Typically: ID | Name | (optional position)
                player_link = cells[0].find('a')
                if player_link:
                    player_name = player_link.get_text(strip=True)
                    # Try to extract position (1-5) if available
                    position = None
                    if len(cells) >= 3:
                        pos_text = cells[2].get_text(strip=True)
                        if pos_text.isdigit() and 1 <= int(pos_text) <= 5:
                            position = int(pos_text)
                    
                    roster_players.append({
                        "name": player_name,
                        "position": position
                    })
    
    # Limit to 5 active players
    return roster_players[:5]

def get_team_roster(team_name: str) -> List[Dict]:
    """
    Get current roster for a team (cached for 7 days).
    
    Args:
        team_name: Team name from Liquipedia API (e.g., "Team Spirit")
    
    Returns:
        List of player dicts: [{'name': str, 'position': int | None}, ...]
        Empty list if team not found or scraping fails.
    """
    _load_cache()
    
    # Check cache
    cache_entry = _roster_cache.get(team_name)
    if cache_entry:
        cached_at = datetime.fromisoformat(cache_entry["cached_at"])
        if datetime.now() - cached_at < timedelta(days=CACHE_TTL_DAYS):
            return cache_entry["players"]
    
    # Scrape roster
    _rate_limit()
    
    normalized = _normalize_team_name(team_name)
    url = f"{BASE_URL}/{normalized}"
    
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        players = _parse_roster(resp.text)
        
        # Cache result
        _roster_cache[team_name] = {
            "players": players,
            "cached_at": datetime.now().isoformat(),
            "liquipedia_url": url
        }
        _save_cache()
        
        return players
    
    except (requests.exceptions.RequestException, Exception) as e:
        print(f"  Failed to scrape {team_name}: {e}")
        return []
