"""
Evaluate the new Glicko features against a Logistic Regression baseline.

We will merge the Glicko features onto the matches and perform a time-based
80/20 train/test split. We evaluate using Log Loss (primary) and AUC.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score, accuracy_score

def main():
    # Load matches and glicko features
    matches = pd.read_csv("data/processed/matches.csv", parse_dates=["start_time"])
    glicko = pd.read_csv("data/features/match_glicko.csv")

    # Merge
    df = matches.merge(glicko, on="match_id")

    # Sort chronologically to prevent temporal leakage
    df = df.sort_values("start_time").reset_index(drop=True)

    # To have a fair comparison, we only want to evaluate on matches where both teams
    # have stabilized ratings. Glicko initializes at RD=350. Let's filter out matches
    # where the team's RD is extremely high (meaning players have no history).
    # Since initial RD is 350, let's filter where both teams have an RD < 340
    # which roughly equates to having played at least a few matches.
    df_stable = df[(df["radiant_glicko_rd"] < 340) & (df["dire_glicko_rd"] < 340)].copy()

    print(f"Total matches: {len(df)}")
    print(f"Matches with stable ratings: {len(df_stable)}")

    # Train/Test Split (80/20)
    split_idx = int(len(df_stable) * 0.8)
    train_df = df_stable.iloc[:split_idx]
    test_df = df_stable.iloc[split_idx:]

    print(f"Train matches: {len(train_df)} ({train_df['start_time'].min()} to {train_df['start_time'].max()})")
    print(f"Test matches:  {len(test_df)} ({test_df['start_time'].min()} to {test_df['start_time'].max()})")

    # Features
    # 'glicko_win_prob' is already our model's pre-computed mathematical probability
    # 'glicko_rating_diff' is the raw difference (radiant - dire)
    features = ["glicko_rating_diff", "glicko_win_prob"]

    X_train = train_df[features]
    y_train = train_df["radiant_win"]

    X_test = test_df[features]
    y_test = test_df["radiant_win"]

    # Baseline: Always predict 0.5
    baseline_pred = np.full_like(y_test, 0.5, dtype=float)
    baseline_logloss = log_loss(y_test, baseline_pred)

    print(f"\n--- Results ---")
    print(f"Baseline (0.5) Log Loss:     {baseline_logloss:.4f}")

    # Model 1: Logistic Regression using just the mathematical Glicko win probability
    # Pass it as a single feature.
    clf1 = LogisticRegression()
    clf1.fit(X_train[["glicko_win_prob"]], y_train)
    pred1 = clf1.predict_proba(X_test[["glicko_win_prob"]])[:, 1]

    print(f"Glicko Prob Log Loss:        {log_loss(y_test, pred1):.4f}")
    print(f"Glicko Prob AUC:             {roc_auc_score(y_test, pred1):.4f}")
    print(f"Glicko Prob Accuracy:        {accuracy_score(y_test, pred1 > 0.5):.4f}")

    # Output the pure Glicko formula's log loss (without logistic regression recalibration)
    pure_glicko_pred = X_test["glicko_win_prob"].clip(0.01, 0.99) # Clip to avoid infinite log loss
    print(f"Pure Math Glicko Log Loss:   {log_loss(y_test, pure_glicko_pred):.4f}")

if __name__ == "__main__":
    main()
