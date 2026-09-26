"""
Player mapping utilities for bridging Liquipedia to OpenDota.
Uses exact + fuzzy name matching against OpenDota player database.
"""
import pandas as pd
import os
import csv
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional, List, Dict

_lookup_cache = None
_log_file = None

def _load_lookup():
    """Load OpenDota player lookup for matching."""
    global _lookup_cache
    if _lookup_cache is None:
        lookup_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "players_lookup.csv")
        if os.path.exists(lookup_path):
            _lookup_cache = pd.read_csv(lookup_path)
        else:
            _lookup_cache = pd.DataFrame(columns=["account_id", "name"])
    return _lookup_cache

def _get_log_file():
    """Get absolute path to player mapping log."""
    global _log_file
    if _log_file is None:
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        _log_file = os.path.join(log_dir, "player_mapping.csv")
        # Create header if new file
        if not os.path.exists(_log_file):
            with open(_log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "team", "player_name", "status", "matched_name", "confidence", "account_id"])
    return _log_file

def _log_mapping(team: str, player_name: str, status: str, matched_name: str = "", confidence: float = 0.0, account_id: Optional[int] = None):
    """Log a player mapping result to CSV."""
    log_path = _get_log_file()
    with open(log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            team,
            player_name,
            status,
            matched_name,
            f"{confidence:.2f}" if confidence else "",
            account_id if account_id else ""
        ])

def normalize_name(name: str) -> str:
    """Normalize player names for fuzzy matching."""
    if pd.isna(name):
        return ""
    return str(name).lower().strip().replace("_", "").replace("-", "").replace(" ", "")

def similarity(a: str, b: str) -> float:
    """Calculate string similarity."""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()

def map_liquipedia_to_opendota(liq_player_name: str, team_name: str = "") -> Optional[int]:
    """
    Map Liquipedia player name to OpenDota account ID.
    
    Args:
        liq_player_name: Player name from Liquipedia roster
        team_name: Team name for logging purposes
    
    Returns:
        OpenDota account_id if found, None otherwise
    """
    # 1. Exact match
    lookup = _load_lookup()
    exact = lookup[lookup["name"].str.lower() == liq_player_name.lower()]
    if not exact.empty:
        account_id = int(exact.iloc[0]["account_id"])
        _log_mapping(team_name, liq_player_name, "exact_match", exact.iloc[0]["name"], 1.0, account_id)
        return account_id
    
    # 2. Fuzzy match (85% threshold)
    best_match = None
    best_score = 0.0
    
    for _, row in lookup.iterrows():
        if pd.isna(row["name"]):
            continue
        score = similarity(liq_player_name, row["name"])
        if score > best_score:
            best_score = score
            best_match = row
    
    if best_match is not None and best_score >= 0.85:
        account_id = int(best_match["account_id"])
        _log_mapping(team_name, liq_player_name, "fuzzy_match", best_match["name"], best_score, account_id)
        print(f"  Fuzzy match: {liq_player_name} → {best_match['name']} ({best_score:.2%})")
        return account_id
    
    # 3. Unknown player
    _log_mapping(team_name, liq_player_name, "unmapped")
    print(f"  Unmapped player: {liq_player_name} (team: {team_name})")
    return None

def map_team_roster(team_name: str, liq_players: List[Dict]) -> Optional[List[int]]:
    """
    Map a full team roster from Liquipedia to OpenDota account IDs.
    
    Args:
        team_name: Team name for logging
        liq_players: List of player dicts with 'name' and optional 'position'
    
    Returns:
        List of 5 account_ids if all mapped, None if incomplete roster
    """
    account_ids = []
    for player in liq_players:
        account_id = map_liquipedia_to_opendota(player["name"], team_name)
        if account_id:
            account_ids.append(account_id)
    
    # Require complete roster (5 players)
    if len(account_ids) == 5:
        return account_ids
    
    print(f"  Skipping {team_name}: incomplete roster ({len(account_ids)}/5 mapped)")
    return None
