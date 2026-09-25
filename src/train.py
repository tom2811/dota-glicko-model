import pandas as pd
import numpy as np
from scipy.special import expit
from sklearn.metrics import log_loss, roc_auc_score, accuracy_score
from sklearn.ensemble import GradientBoostingClassifier
import warnings

def compute_player_features():
    df = pd.read_csv("data/processed/match_players.csv", parse_dates=["start_time"])
    df = df.sort_values(["account_id", "start_time"])
    df["prev_match_time"] = df.groupby("account_id")["start_time"].shift(1)
    df["rest_days"] = (df["start_time"] - df["prev_match_time"]).dt.total_seconds() / (24 * 3600)
    df["rest_days"] = df["rest_days"].fillna(30.0).clip(upper=30.0)
    df = df.set_index("start_time")
    def count_last_7_days(group):
        return group["match_id"].rolling('7D').count() - 1
    df["matches_last_7_days"] = df.groupby("account_id", group_keys=False).apply(count_last_7_days)
    df = df.reset_index()
    return df

def create_team_features(df_players):
    radiant = df_players[df_players["is_radiant"] == True]
    dire = df_players[df_players["is_radiant"] == False]
    def aggregate_team(df_side, prefix):
        agg = df_side.groupby("match_id").agg(
            rest_days_mean=("rest_days", "mean"),
            matches_last_7_days_mean=("matches_last_7_days", "mean")
        ).reset_index()
        rename_dict = {c: f"{prefix}_{c}" for c in agg.columns if c != "match_id"}
        return agg.rename(columns=rename_dict)
    rad_agg = aggregate_team(radiant, "radiant")
    dire_agg = aggregate_team(dire, "dire")
    return pd.merge(rad_agg, dire_agg, on="match_id")

class GlickoInit:
    def fit(self, X, y, sample_weight=None):
        return self

    def predict_proba(self, X):
        # Assume the last column of X is the raw glicko_win_prob
        probs = X[:, -1]
        # Return [P(win=0), P(win=1)]
        return np.vstack([1 - probs, probs]).T

def main():
    warnings.simplefilter(action='ignore')

    print("Computing scheduling features...")
    df_players = compute_player_features()
    team_features = create_team_features(df_players)
    matches = pd.read_csv("data/processed/matches.csv", parse_dates=["start_time"])
    glicko = pd.read_csv("data/features/match_glicko.csv")
    df = matches.merge(glicko, on="match_id").merge(team_features, on="match_id")
    df = df.sort_values("start_time").reset_index(drop=True)
    df_stable = df[(df["radiant_glicko_rd"] < 340) & (df["dire_glicko_rd"] < 340)].copy()

    split_idx = int(len(df_stable) * 0.8)
    train_df = df_stable.iloc[:split_idx]
    test_df = df_stable.iloc[split_idx:]

    train_df["rest_days_diff"] = train_df["radiant_rest_days_mean"] - train_df["dire_rest_days_mean"]
    test_df["rest_days_diff"] = test_df["radiant_rest_days_mean"] - test_df["dire_rest_days_mean"]
    train_df["matches_7d_diff"] = train_df["radiant_matches_last_7_days_mean"] - train_df["dire_matches_last_7_days_mean"]
    test_df["matches_7d_diff"] = test_df["radiant_matches_last_7_days_mean"] - test_df["dire_matches_last_7_days_mean"]

    train_df["core_rating_diff"] = train_df["radiant_core_rating"] - train_df["dire_core_rating"]
    test_df["core_rating_diff"] = test_df["radiant_core_rating"] - test_df["dire_core_rating"]
    train_df["support_rating_diff"] = train_df["radiant_support_rating"] - train_df["dire_support_rating"]
    test_df["support_rating_diff"] = test_df["radiant_support_rating"] - test_df["dire_support_rating"]

    # Clip prob exactly as before to avoid math issues
    train_df["glicko_win_prob"] = train_df["glicko_win_prob"].clip(0.01, 0.99)
    test_df["glicko_win_prob"] = test_df["glicko_win_prob"].clip(0.01, 0.99)

    features = [
        "rest_days_diff",
        "matches_7d_diff",
        "radiant_rest_days_mean",
        "dire_rest_days_mean",
        "radiant_matches_last_7_days_mean",
        "dire_matches_last_7_days_mean",
        "core_rating_diff",
        "support_rating_diff",
        "glicko_win_prob" # CRITICAL: must be the LAST feature for GlickoInit
    ]

    X_train = train_df[features].values
    y_train = train_df["radiant_win"].astype(int).values

    X_test = test_df[features].values
    y_test = test_df["radiant_win"].astype(int).values

    print("\nTraining scikit-learn GradientBoostingClassifier with Glicko init...")
    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=2,
        learning_rate=0.01,
        random_state=42,
        init=GlickoInit()
    )

    model.fit(X_train, y_train)
    probs = model.predict_proba(X_test)[:, 1]

    print("\n--- Model Results ---")
    print(f"Test Log Loss: {log_loss(y_test, probs):.4f}")
    print(f"Test AUC:      {roc_auc_score(y_test, probs):.4f}")

    pure_glicko_probs = test_df["glicko_win_prob"]
    print(f"Pure Glicko Baseline Log Loss: {log_loss(y_test, pure_glicko_probs):.4f}")

if __name__ == "__main__":
    main()
