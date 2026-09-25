import requests
import pandas as pd
import time
from datetime import datetime, timedelta, timezone
import os

BASE = "https://api.opendota.com/api"
WINDOW_DAYS = 365

def get_pro_matches_page(less_than_match_id=None, max_retries=5):
    params = {"less_than_match_id": less_than_match_id} if less_than_match_id else {}
    for attempt in range(max_retries):
        resp = requests.get(f"{BASE}/proMatches", params=params)
        if resp.status_code == 429:
            wait = 60  # Wait a full minute for the quota to reset
            print(f"  rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"gave up on page after {max_retries} retries (cursor={less_than_match_id})")

def main():
    print(f"Fetching /proMatches for the last {WINDOW_DAYS} days...")
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    all_matches = []
    cursor = None
    page = 0

    while True:
        page += 1
        batch = get_pro_matches_page(cursor)
        if not batch:
            break

        batch_df = pd.DataFrame(batch)
        batch_df['start_time'] = pd.to_datetime(batch_df['start_time'], unit='s', utc=True)
        in_window = batch_df[batch_df['start_time'] >= cutoff]
        all_matches.append(in_window)

        oldest_in_batch = batch_df['start_time'].min()
        print(f"page {page}: {len(batch)} matches, oldest={oldest_in_batch.date()}")

        if oldest_in_batch < cutoff:
            break

        cursor = batch_df['match_id'].iloc[-1]
        time.sleep(1.1)

    df_matches = pd.concat(all_matches, ignore_index=True)
    print(f"\nTotal matches in {WINDOW_DAYS}-day window: {len(df_matches)}")

    # Filter by professional tier
    print("Fetching /leagues to filter by professional tier...")
    resp = requests.get(f"{BASE}/leagues")
    resp.raise_for_status()
    all_leagues = pd.DataFrame(resp.json())
    professional_leagueids = set(all_leagues[all_leagues['tier'] == 'professional']['leagueid'])

    MANUALLY_EXCLUDED_LEAGUEIDS = {20176}  # BETBOOM Streamers Battle

    df_tier_filtered = df_matches[
        df_matches['leagueid'].isin(professional_leagueids)
        & ~df_matches['leagueid'].isin(MANUALLY_EXCLUDED_LEAGUEIDS)
    ].copy()

    print(f"Matches after professional league filter: {len(df_tier_filtered)}")

    # Minimum match threshold (5)
    MIN_MATCHES = 5
    team_appearances = pd.concat([
        df_tier_filtered['radiant_team_id'], df_tier_filtered['dire_team_id']
    ]).value_counts()
    qualifying_teams = team_appearances[team_appearances >= MIN_MATCHES].index

    df_reliable = df_tier_filtered[
        df_tier_filtered['radiant_team_id'].isin(qualifying_teams)
        & df_tier_filtered['dire_team_id'].isin(qualifying_teams)
    ].copy()

    print(f"Matches after team MIN_MATCHES filter: {len(df_reliable)}")

    # Save the output
    os.makedirs("data", exist_ok=True)
    cols_to_save = [
        "match_id", "start_time", "leagueid", "league_name", "series_type",
        "radiant_team_id", "radiant_name", "dire_team_id", "dire_name",
        "radiant_win"
    ]
    # Only save columns that exist in the DataFrame
    cols_present = [c for c in cols_to_save if c in df_reliable.columns]
    df_reliable = df_reliable[cols_present]
    df_reliable.to_csv("data/raw/pro_matches_raw.csv", index=False)
    print("Saved data/pro_matches_raw.csv.")

if __name__ == "__main__":
    main()
