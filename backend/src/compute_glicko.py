import pandas as pd
import numpy as np
import os
import math

# Glicko-1 hyperparameters
C = 35.0  # uncertainty growth over time (approx: sqrt((350^2 - 40^2) / 365) = 18.2, but typical is 35-50)
RD_INIT = 350.0
R_INIT = 1500.0
Q = np.log(10) / 400.0

def g(rd):
    return 1.0 / math.sqrt(1.0 + 3.0 * (Q ** 2) * (rd ** 2) / (math.pi ** 2))

def E(r, r_opponent, rd_opponent):
    return 1.0 / (1.0 + 10.0 ** (-g(rd_opponent) * (r - r_opponent) / 400.0))

def main():
    print("Loading match players...")
    mp = pd.read_csv("data/processed/match_players.csv", parse_dates=["start_time"])
    mp = mp.sort_values(["start_time", "match_id", "player_slot"])
    
    # Track ratings: account_id -> {"r": 1500, "rd": 350, "last_time": dt}
    ratings = {}
    
    # For output
    out_rows = []
    
    # Process match by match
    groups = mp.groupby("match_id", sort=False)
    
    for match_id, group in groups:
        match_time = group["start_time"].iloc[0]
        
        # Apply time decay to RD for all players in this match
        for _, row in group.iterrows():
            pid = row["account_id"]
            if pid not in ratings:
                ratings[pid] = {"r": R_INIT, "rd": RD_INIT, "last_time": match_time}
            else:
                days_since = (match_time - ratings[pid]["last_time"]).total_seconds() / (24*3600)
                if days_since > 0:
                    new_rd = math.sqrt(ratings[pid]["rd"]**2 + (C**2)*days_since)
                    ratings[pid]["rd"] = min(new_rd, RD_INIT)
                ratings[pid]["last_time"] = match_time

        radiant = group[group["is_radiant"] == True]
        dire = group[group["is_radiant"] == False]
        
        # If a team has 0 players (data error), skip
        if len(radiant) == 0 or len(dire) == 0:
            continue
            
        # Aggregate team ratings (average)
        rad_r = radiant["account_id"].apply(lambda p: ratings[p]["r"]).mean()
        rad_rd = radiant["account_id"].apply(lambda p: ratings[p]["rd"]).mean()
        
        dire_r = dire["account_id"].apply(lambda p: ratings[p]["r"]).mean()
        dire_rd = dire["account_id"].apply(lambda p: ratings[p]["rd"]).mean()
        
        # Pre-match win prob
        win_prob = E(rad_r, dire_r, dire_rd)
        
        # Role-based aggregates
        # Core = fantasy_role == 1, Support = fantasy_role == 2
        rad_cores = radiant[radiant["fantasy_role"] == 1]
        rad_supps = radiant[radiant["fantasy_role"] == 2]
        
        rad_core_r = rad_cores["account_id"].apply(lambda p: ratings[p]["r"]).mean() if len(rad_cores) > 0 else rad_r
        rad_supp_r = rad_supps["account_id"].apply(lambda p: ratings[p]["r"]).mean() if len(rad_supps) > 0 else rad_r
        
        dire_cores = dire[dire["fantasy_role"] == 1]
        dire_supps = dire[dire["fantasy_role"] == 2]
        
        dire_core_r = dire_cores["account_id"].apply(lambda p: ratings[p]["r"]).mean() if len(dire_cores) > 0 else dire_r
        dire_supp_r = dire_supps["account_id"].apply(lambda p: ratings[p]["r"]).mean() if len(dire_supps) > 0 else dire_r
        
        out_rows.append({
            "match_id": match_id,
            "radiant_glicko_rating": rad_r,
            "radiant_glicko_rd": rad_rd,
            "radiant_core_rating": rad_core_r,
            "radiant_support_rating": rad_supp_r,
            "dire_glicko_rating": dire_r,
            "dire_glicko_rd": dire_rd,
            "dire_core_rating": dire_core_r,
            "dire_support_rating": dire_supp_r,
            "glicko_win_prob": win_prob,
            "glicko_rating_diff": rad_r - dire_r
        })
        
        # Update ratings
        # Treating it as a single match between rad_r/rad_rd and dire_r/dire_rd,
        # then apply the delta to each player
        rad_win = 1 if radiant["win"].iloc[0] else 0
        dire_win = 1 - rad_win
        
        # For each radiant player, they played against dire team
        for _, row in radiant.iterrows():
            pid = row["account_id"]
            r, rd = ratings[pid]["r"], ratings[pid]["rd"]
            g_rd_opp = g(dire_rd)
            E_val = E(r, dire_r, dire_rd)
            d2 = 1.0 / ((Q**2) * (g_rd_opp**2) * E_val * (1 - E_val))
            
            denom = 1.0 / (rd**2) + 1.0 / d2
            r_new = r + Q / denom * g_rd_opp * (rad_win - E_val)
            rd_new = math.sqrt(1.0 / denom)
            
            ratings[pid]["r"] = r_new
            ratings[pid]["rd"] = rd_new
            
        # For each dire player, they played against radiant team
        for _, row in dire.iterrows():
            pid = row["account_id"]
            r, rd = ratings[pid]["r"], ratings[pid]["rd"]
            g_rd_opp = g(rad_rd)
            E_val = E(r, rad_r, rad_rd)
            d2 = 1.0 / ((Q**2) * (g_rd_opp**2) * E_val * (1 - E_val))
            
            denom = 1.0 / (rd**2) + 1.0 / d2
            r_new = r + Q / denom * g_rd_opp * (dire_win - E_val)
            rd_new = math.sqrt(1.0 / denom)
            
            ratings[pid]["r"] = r_new
            ratings[pid]["rd"] = rd_new

    out_df = pd.DataFrame(out_rows)
    os.makedirs("data/features", exist_ok=True)
    out_df.to_csv("data/features/match_glicko.csv", index=False)
    print("Saved data/features/match_glicko.csv")
    
    # NEW: Save final player ratings for the API
    final_ratings = [{"account_id": k, "r": v["r"], "rd": v["rd"]} for k, v in ratings.items()]
    pd.DataFrame(final_ratings).to_csv("data/features/final_player_ratings.csv", index=False)
    print("Saved data/features/final_player_ratings.csv")
    
if __name__ == "__main__":
    main()
