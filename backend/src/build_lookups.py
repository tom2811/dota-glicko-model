#!/usr/bin/env python3
"""Parse pro_players.json into players_lookup.csv"""
import json
import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

with open(RAW_DIR / "pro_players.json") as f:
    players = json.load(f)

# Extract only needed columns
df = pd.DataFrame([
    {
        "account_id": p["account_id"],
        "name": p.get("name", ""),
        "team_name": p.get("team_name", ""),
        "team_id": p.get("team_id", 0),
        "fantasy_role": p.get("fantasy_role")
    }
    for p in players
])

df.to_csv(PROCESSED_DIR / "players_lookup.csv", index=False)
print(f"✓ Wrote {len(df)} players to players_lookup.csv")
