"""
Extended data collector: fetch per-player records from /matches/{id}.

Reads match IDs from the existing pro_matches_raw.csv (already filtered to
professional, tier-qualified, MIN_MATCHES-qualifying matches) and fetches the
full player array from each match detail.

Stores the results in data/raw/match_detail_cache_v3.jsonl — one JSON line per
match, each containing the match-level metadata plus a 10-element player array.
This cache is strictly append-only and resumable: if interrupted, re-running
picks up where it left off.

Usage:
    .venv/bin/python collect_player_data.py
"""

import json
import os
import sys
import time

import pandas as pd
import requests

BASE = "https://api.opendota.com/api"

# --------------------------------------------------------------------------- #
# API helpers (same backoff pattern as fetch_pro_matches.py)
# --------------------------------------------------------------------------- #

def fetch_match_detail(match_id: int, max_retries: int = 5) -> dict:
    """Fetch /matches/{id} with retry on HTTP 429."""
    for attempt in range(max_retries):
        resp = requests.get(f"{BASE}/matches/{match_id}")
        if resp.status_code == 429:
            wait = 5 * (attempt + 1)
            print(f"  rate limited on {match_id}, waiting {wait}s "
                  f"(attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(
        f"gave up on {match_id} after {max_retries} retries (all 429s)"
    )


def extract_player_records(match_data: dict) -> list[dict]:
    """
    Extract the fields we care about from each player in the match.

    We store enough to build:
    - match_players.csv  (identity + side + outcome)
    - future Glicko/Elo  (who played, who won)

    Deliberately excluded:
    - hero_id          (spec says no draft info yet)
    - lane_role        (unreliable in pro matches)
    - in-game stats    (prediction is pre-match only)
    """
    players = match_data.get("players", [])
    records = []
    for p in players:
        records.append({
            "account_id": p.get("account_id"),
            "player_slot": p.get("player_slot"),
            "is_radiant": p.get("isRadiant"),
            "personaname": p.get("personaname"),
        })
    return records


def build_cache_record(match_id: int, match_data: dict) -> dict:
    """Build the JSON record we store in the v3 cache."""
    return {
        "match_id": match_id,
        "start_time": match_data.get("start_time"),
        "duration": match_data.get("duration"),
        "radiant_win": match_data.get("radiant_win"),
        "series_id": match_data.get("series_id"),
        "series_type": match_data.get("series_type"),
        "leagueid": match_data.get("leagueid"),
        "patch": match_data.get("patch"),
        "radiant_team_id": match_data.get("radiant_team_id"),
        "dire_team_id": match_data.get("dire_team_id"),
        "players": extract_player_records(match_data),
    }


# --------------------------------------------------------------------------- #
# Main collection loop
# --------------------------------------------------------------------------- #

def main():
    # ---- Determine which match IDs we need -------------------------------- #
    csv_path = "data/raw/pro_matches_raw.csv"
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found. Run fetch_pro_matches.py first.")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    target_ids = df["match_id"].unique().tolist()
    print(f"target match IDs from {csv_path}: {len(target_ids)}")

    # ---- Load existing v3 cache (resumable) ------------------------------- #
    cache_path = "data/raw/match_detail_cache_v3.jsonl"
    os.makedirs("data/raw", exist_ok=True)

    seen_ids: set[int] = set()
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            for line in f:
                rec = json.loads(line)
                seen_ids.add(rec["match_id"])
        print(f"resuming: {len(seen_ids)} already cached in v3")

    to_fetch = [mid for mid in target_ids if mid not in seen_ids]
    print(f"remaining to fetch: {len(to_fetch)}")

    if not to_fetch:
        print("nothing to fetch — cache is complete")
        return

    # ---- Fetch and cache -------------------------------------------------- #
    fetched = 0
    failed = 0
    total = len(to_fetch)

    with open(cache_path, "a") as f:
        for i, match_id in enumerate(to_fetch):
            try:
                data = fetch_match_detail(match_id)
                rec = build_cache_record(match_id, data)
                f.write(json.dumps(rec) + "\n")
                f.flush()  # ensure each line is durable on disk
                fetched += 1
            except Exception as e:
                print(f"  FAILED {match_id}: {e}")
                failed += 1

            if (i + 1) % 50 == 0 or i == total - 1:
                print(f"progress: {i+1}/{total} "
                      f"(fetched={fetched}, failed={failed})")

            # stay well under the free-tier rate limit (~60 req/min)
            time.sleep(1.5)

    print(f"\ndone: fetched={fetched}, failed={failed}, "
          f"total cached={len(seen_ids) + fetched}")


if __name__ == "__main__":
    main()
