"""
Build relational datasets from the raw v3 match detail cache.

Reads data/raw/match_detail_cache_v3.jsonl and produces:
  - data/processed/matches.csv       (one row per match)
  - data/processed/match_players.csv (one row per player per match)
  - data/processed/leagues.csv       (one row per league, fetched from API)

This is a fast, offline transformation (no API calls needed for matches/players).
The leagues endpoint is called once to enrich with tier information.

Usage:
    .venv/bin/python build_datasets.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests

BASE = "https://api.opendota.com/api"

# --------------------------------------------------------------------------- #
# Leagues (one-time API call, small payload)
# --------------------------------------------------------------------------- #

def fetch_leagues() -> pd.DataFrame:
    """Fetch /leagues and return as DataFrame."""
    print("fetching /leagues from OpenDota...")
    resp = requests.get(f"{BASE}/leagues")
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    return df[["leagueid", "name", "tier"]].rename(columns={"name": "league_name"})


# --------------------------------------------------------------------------- #
# Build matches.csv from cache
# --------------------------------------------------------------------------- #

def build_matches(cache_records: list[dict]) -> pd.DataFrame:
    """Build match-level dataset from raw cache records."""
    rows = []
    for rec in cache_records:
        rows.append({
            "match_id": rec["match_id"],
            "start_time": rec["start_time"],
            "duration": rec.get("duration"),
            "leagueid": rec.get("leagueid"),
            "series_id": rec.get("series_id"),
            "series_type": rec.get("series_type"),
            "radiant_team_id": rec.get("radiant_team_id"),
            "dire_team_id": rec.get("dire_team_id"),
            "radiant_win": rec.get("radiant_win"),
            "patch": rec.get("patch"),
        })

    df = pd.DataFrame(rows)

    # Convert start_time from Unix epoch to datetime
    df["start_time"] = pd.to_datetime(df["start_time"], unit="s", utc=True)
    df = df.sort_values("start_time").reset_index(drop=True)

    return df


# --------------------------------------------------------------------------- #
# Build match_players.csv from cache
# --------------------------------------------------------------------------- #

def build_match_players(cache_records: list[dict]) -> pd.DataFrame:
    """
    Build player-level dataset from raw cache records.

    Each match produces up to 10 rows (5 radiant + 5 dire).
    Players without account_id (anonymous/bot) are dropped.
    """
    rows = []
    for rec in cache_records:
        match_id = rec["match_id"]
        start_time = rec["start_time"]
        radiant_win = rec.get("radiant_win")
        radiant_team_id = rec.get("radiant_team_id")
        dire_team_id = rec.get("dire_team_id")

        for p in rec.get("players", []):
            account_id = p.get("account_id")
            if account_id is None:
                continue  # skip anonymous players

            is_radiant = p.get("is_radiant")
            team_id = radiant_team_id if is_radiant else dire_team_id

            # derive win from side + match outcome
            if radiant_win is not None and is_radiant is not None:
                win = radiant_win if is_radiant else not radiant_win
            else:
                win = None

            rows.append({
                "match_id": match_id,
                "account_id": account_id,
                "player_slot": p.get("player_slot"),
                "is_radiant": is_radiant,
                "team_id": team_id,
                "win": win,
                "start_time": start_time,
            })

    df = pd.DataFrame(rows)

    # Convert start_time from Unix epoch to datetime
    df["start_time"] = pd.to_datetime(df["start_time"], unit="s", utc=True)
    df = df.sort_values(["start_time", "match_id", "player_slot"]).reset_index(drop=True)

    # Load pro_players.json to merge fantasy_role
    try:
        with open("data/raw/pro_players.json") as f:
            pro_players = json.load(f)
        role_map = {p["account_id"]: p.get("fantasy_role") for p in pro_players if p.get("account_id")}
        df["fantasy_role"] = df["account_id"].map(role_map)
    except FileNotFoundError:
        print("⚠ data/raw/pro_players.json not found, fantasy_role will be NaN")
        df["fantasy_role"] = None

    return df


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    cache_path = "data/raw/match_detail_cache_v3.jsonl"
    if not os.path.exists(cache_path):
        print(f"ERROR: {cache_path} not found. Run collect_player_data.py first.")
        sys.exit(1)

    # ---- Load cache ------------------------------------------------------- #
    cache_records = []
    with open(cache_path) as f:
        for line in f:
            cache_records.append(json.loads(line))
    print(f"loaded {len(cache_records)} records from {cache_path}")

    os.makedirs("data/processed", exist_ok=True)

    # ---- Build matches.csv ------------------------------------------------ #
    df_matches = build_matches(cache_records)
    matches_path = "data/processed/matches.csv"
    df_matches.to_csv(matches_path, index=False)
    print(f"\nsaved {matches_path}")
    print(f"  rows: {len(df_matches)}")
    print(f"  date range: {df_matches['start_time'].min()} to "
          f"{df_matches['start_time'].max()}")
    print(f"  unique teams: {pd.concat([df_matches['radiant_team_id'], df_matches['dire_team_id']]).nunique()}")

    # ---- Build match_players.csv ------------------------------------------ #
    df_players = build_match_players(cache_records)
    players_path = "data/processed/match_players.csv"
    df_players.to_csv(players_path, index=False)
    print(f"\nsaved {players_path}")
    print(f"  rows: {len(df_players)}")
    print(f"  unique players: {df_players['account_id'].nunique()}")
    print(f"  players per match (median): "
          f"{df_players.groupby('match_id').size().median():.0f}")

    # Sanity check: do we have 10 players per match?
    players_per_match = df_players.groupby("match_id").size()
    incomplete = (players_per_match < 10).sum()
    if incomplete > 0:
        print(f"  ⚠ {incomplete} matches have <10 identified players "
              f"(likely anonymous accounts)")

    # ---- Build leagues.csv ------------------------------------------------ #
    try:
        df_leagues = fetch_leagues()
        # Only keep leagues that appear in our dataset
        our_league_ids = df_matches["leagueid"].unique()
        df_leagues_filtered = df_leagues[
            df_leagues["leagueid"].isin(our_league_ids)
        ].copy()
        leagues_path = "data/processed/leagues.csv"
        df_leagues_filtered.to_csv(leagues_path, index=False)
        print(f"\nsaved {leagues_path}")
        print(f"  leagues in dataset: {len(df_leagues_filtered)}")
        print(df_leagues_filtered[["leagueid", "league_name", "tier"]]
              .to_string(index=False))
    except Exception as e:
        print(f"\n⚠ could not fetch leagues (network error): {e}")
        print("  skipping leagues.csv — run again when online")

    # ---- Summary ---------------------------------------------------------- #
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    print(f"  matches.csv:       {len(df_matches):,} matches")
    print(f"  match_players.csv: {len(df_players):,} player records")
    print(f"  unique players:    {df_players['account_id'].nunique():,}")
    print(f"  date range:        {df_matches['start_time'].min().date()} to "
          f"{df_matches['start_time'].max().date()}")
    print()
    print("Next step: build Glicko/Elo ratings from match_players.csv")


if __name__ == "__main__":
    main()
