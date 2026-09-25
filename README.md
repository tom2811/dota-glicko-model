# dota-glicko-model

Predicts pro Dota 2 matches using player-level Glicko ratings, schedule fatigue, and role-based weights.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
python3 run.py          # fetch data + train
python3 run.py data     # fetch and process data only
python3 run.py train    # train model only
```

Or run steps individually:

1. `python src/fetch_pro_matches.py` — pull match metadata
2. `python src/fetch_pro_players.py` — pull player roles
3. `python src/collect_player_data.py` — pull rosters
4. `python src/build_datasets.py` — build csvs
5. `python src/compute_glicko.py` — build ratings
6. `python src/train.py` — train model

## How the Model Works

The model is a `GradientBoostingClassifier` that predicts radiant win probability using **both** Glicko ratings and schedule features.

A custom `GlickoInit` estimator provides the starting prediction from `glicko_win_prob`, and the boosting trees learn residual corrections from the additional features:

| Feature                            | Description                                         |
| ---------------------------------- | --------------------------------------------------- |
| `glicko_win_prob`                  | Pre-computed Glicko win probability (baseline)      |
| `core_rating_diff`                 | Radiant − Dire core role Glicko rating              |
| `support_rating_diff`              | Radiant − Dire support role Glicko rating           |
| `rest_days_diff`                   | Radiant − Dire mean rest days                       |
| `matches_7d_diff`                  | Radiant − Dire mean matches in last 7 days          |
| `radiant_rest_days_mean`           | Radiant average days since each player's last match |
| `dire_rest_days_mean`              | Dire average days since each player's last match    |
| `radiant_matches_last_7_days_mean` | Radiant average recent match load                   |
| `dire_matches_last_7_days_mean`    | Dire average recent match load                      |

## Data Cleaning

### League & Match Filtering (`fetch_pro_matches.py`)

- Drops non-professional leagues (`tier != 'professional'`).
- Blacklists exhibition matches (e.g., `20176` Streamers Battle).
- Drops matches where either team has < 5 matches total.

### Roster Integrity (`build_datasets.py`)

- Drops matches without exactly 10 valid `account_id`s.
- Standardizes UNIX timestamps to UTC `datetime`.
- Fills missing `fantasy_role` with `NaN`.

### Mathematical Safeguards (`compute_glicko.py`)

- Enforces chronological sorting by `start_time` (prevents data leaks).
- Caps `RD` (rating deviation) at 350.
- Defaults missing `fantasy_role` to team average rating.

### Feature Engineering (`train.py`)

- Clips `rest_days` at 30.0 days.
- Clips `glicko_win_prob` to `[0.01, 0.99]` (prevents infinite logits).
- Drops matches with team `RD > 340` (filters unstable new stacks).
