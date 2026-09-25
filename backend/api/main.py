import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
import os
import sys
import math

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.train import GlickoInit

app = FastAPI(title="Dota 2 Glicko API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = None
player_glicko = {}
player_stats = {}
matches_df = None
match_players_df = None
players_lookup_df = None
final_ratings_df = None

# Glicko parameters needed for win probability math
Q = np.log(10) / 400.0
def g(rd):
    return 1.0 / math.sqrt(1.0 + 3.0 * (Q ** 2) * (rd ** 2) / (math.pi ** 2))

def E(r, r_opponent, rd_opponent):
    return 1.0 / (1.0 + 10.0 ** (-g(rd_opponent) * (r - r_opponent) / 400.0))

@app.on_event("startup")
def load_model():
    global model, player_glicko, player_stats, matches_df, match_players_df, players_lookup_df, final_ratings_df
    base_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
    model_path = os.path.join(base_dir, "model.pkl")
    glicko_path = os.path.join(base_dir, "final_player_ratings.csv")
    stats_path = os.path.join(base_dir, "latest_players.csv")
    
    if os.path.exists(model_path):
        model = joblib.load(model_path)
    if os.path.exists(glicko_path):
        df_g = pd.read_csv(glicko_path)
        player_glicko = df_g.set_index("account_id").to_dict("index")
        final_ratings_df = df_g
    if os.path.exists(stats_path):
        df_s = pd.read_csv(stats_path)
        player_stats = df_s.set_index("account_id").to_dict("index")
    
    # Load match history data
    matches_path = os.path.join(data_dir, "matches.csv")
    match_players_path = os.path.join(data_dir, "match_players.csv")
    players_path = os.path.join(data_dir, "players_lookup.csv")
    
    if os.path.exists(matches_path):
        matches_df = pd.read_csv(matches_path)
        matches_df["start_time"] = pd.to_datetime(matches_df["start_time"])
        matches_df = matches_df.sort_values("start_time", ascending=False)
    if os.path.exists(match_players_path):
        match_players_df = pd.read_csv(match_players_path)
    if os.path.exists(players_path):
        players_lookup_df = pd.read_csv(players_path)

class MatchupRequest(BaseModel):
    radiant_account_ids: list[int]
    dire_account_ids: list[int]

@app.get("/")
def read_root():
    return {"status": "healthy", "model_loaded": model is not None}

@app.get("/upcoming")
def get_upcoming_matches():
    return {
        "matches": [
            {
                "id": "mock-1",
                "radiant_name": "Team Falcons",
                "dire_name": "Xtreme Gaming",
                "radiant_account_ids": [184950344, 102099826, 164532005, 152545459, 136737280],
                "dire_account_ids": [343084576, 377594124, 196400041, 392169957, 392565237]
            },
            {
                "id": "mock-2",
                "radiant_name": "Team Liquid",
                "dire_name": "Gaimin Gladiators",
                "radiant_account_ids": [126212866, 343084576, 392565237, 152859296, 106755427],
                "dire_account_ids": [919735867, 185590374, 957204049, 835864135, 130991304]
            }
        ]
    }

@app.post("/predict")
def predict_match(req: MatchupRequest):
    if not model:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    if len(req.radiant_account_ids) != 5 or len(req.dire_account_ids) != 5:
        raise HTTPException(status_code=400, detail="Must provide exactly 5 players per team")

    def get_player(account_id):
        g = player_glicko.get(account_id, {"r": 1500.0, "rd": 350.0})
        s = player_stats.get(account_id, {"rest_days": 30.0, "matches_last_7_days": 0.0})
        return {"r": g["r"], "rd": g["rd"], "rest": s["rest_days"], "matches": s["matches_last_7_days"]}

    rad = [get_player(aid) for aid in req.radiant_account_ids]
    dire = [get_player(aid) for aid in req.dire_account_ids]

    rad_r = np.mean([p["r"] for p in rad])
    rad_rd = np.mean([p["rd"] for p in rad])
    rad_rest = np.mean([p["rest"] for p in rad])
    rad_matches = np.mean([p["matches"] for p in rad])

    dire_r = np.mean([p["r"] for p in dire])
    dire_rd = np.mean([p["rd"] for p in dire])
    dire_rest = np.mean([p["rest"] for p in dire])
    dire_matches = np.mean([p["matches"] for p in dire])

    # For upcoming match, we don't know roles. Use team average for core/support.
    core_diff = rad_r - dire_r
    supp_diff = rad_r - dire_r
    rest_diff = rad_rest - dire_rest
    matches_diff = rad_matches - dire_matches
    
    win_prob = E(rad_r, dire_r, dire_rd)
    win_prob = np.clip(win_prob, 0.01, 0.99)

    # Features must match train.py order:
    # "rest_days_diff", "matches_7d_diff", "radiant_rest_days_mean", "dire_rest_days_mean",
    # "radiant_matches_last_7_days_mean", "dire_matches_last_7_days_mean", 
    # "core_rating_diff", "support_rating_diff", "glicko_win_prob"
    X = np.array([[
        rest_diff,
        matches_diff,
        rad_rest,
        dire_rest,
        rad_matches,
        dire_matches,
        core_diff,
        supp_diff,
        win_prob
    ]])

    prob = model.predict_proba(X)[0][1]

    return {
        "radiant_win_prob": float(prob),
        "glicko_base_prob": float(win_prob)
    }

@app.get("/matches")
def get_matches(page: int = 1, per_page: int = 20):
    if matches_df is None:
        raise HTTPException(status_code=503, detail="Match data not loaded")
    
    total = len(matches_df)
    start = (page - 1) * per_page
    end = start + per_page
    
    page_matches = matches_df.iloc[start:end]
    
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "matches": [
            {
                "match_id": int(row["match_id"]),
                "date": row["start_time"].isoformat(),
                "radiant_name": row["radiant_name"],
                "dire_name": row["dire_name"],
                "radiant_win": bool(row["radiant_win"]),
                "duration": int(row["duration"]),
                "league_name": row["league_name"]
            }
            for _, row in page_matches.iterrows()
        ]
    }

@app.get("/matches/{match_id}")
def get_match_detail(match_id: int):
    if matches_df is None or match_players_df is None or players_lookup_df is None:
        raise HTTPException(status_code=503, detail="Match data not loaded")
    
    match = matches_df[matches_df["match_id"] == match_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="Match not found")
    
    match_row = match.iloc[0]
    players = match_players_df[match_players_df["match_id"] == match_id]
    
    # Join with player names and Glicko at match time
    def build_roster(is_radiant):
        roster_players = players[players["is_radiant"] == is_radiant].sort_values("player_slot")
        result = []
        for _, p in roster_players.iterrows():
            account_id = int(p["account_id"])
            player_info = players_lookup_df[players_lookup_df["account_id"] == account_id]
            name = player_info.iloc[0]["name"] if not player_info.empty else f"Player {account_id}"
            
            # Derive role from player_slot position (0-4 for radiant, 128-132 for dire)
            slot = int(p["player_slot"])
            position = slot % 128  # 0-4 for both teams
            # Position order: 0=Carry, 1=Mid, 2=Offlane, 3=Soft Supp, 4=Hard Supp
            
            # Glicko at match time would require time-series lookup; use current for now
            glicko = player_glicko.get(account_id, {"r": 1500.0, "rd": 350.0})
            result.append({
                "account_id": account_id,
                "name": name,
                "fantasy_role": position,  # Use position derived from slot
                "glicko_rating": float(glicko["r"]),
                "glicko_rd": float(glicko["rd"])
            })
        return result
    
    return {
        "match_id": int(match_row["match_id"]),
        "date": match_row["start_time"].isoformat(),
        "radiant_name": match_row["radiant_name"],
        "dire_name": match_row["dire_name"],
        "radiant_win": bool(match_row["radiant_win"]),
        "duration": int(match_row["duration"]),
        "league_name": match_row["league_name"],
        "radiant_roster": build_roster(True),
        "dire_roster": build_roster(False)
    }

@app.get("/players")
def get_players():
    if players_lookup_df is None or final_ratings_df is None:
        raise HTTPException(status_code=503, detail="Player data not loaded")
    
    # Merge lookup with current Glicko ratings
    merged = players_lookup_df.merge(
        final_ratings_df[["account_id", "r", "rd"]],
        on="account_id",
        how="left"
    )
    
    # Filter out players without ratings
    merged = merged.dropna(subset=["r"])
    merged = merged.sort_values("r", ascending=False)
    
    return {
        "players": [
            {
                "account_id": int(row["account_id"]),
                "name": row["name"],
                "team_name": row["team_name"] if pd.notna(row["team_name"]) else "",
                "fantasy_role": int(row["fantasy_role"]) if pd.notna(row["fantasy_role"]) else None,
                "glicko_rating": float(row["r"]),
                "glicko_rd": float(row["rd"])
            }
            for _, row in merged.iterrows()
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
