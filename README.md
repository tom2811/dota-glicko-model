# dota-glicko-model

Predicts pro Dota 2 matches using player-level Glicko ratings, schedule fatigue, and role-based weights. Includes web application with upcoming match predictions and live match tracking.

## Quick Start

### Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run Data Pipeline
```bash
python3 run.py          # fetch data + train
python3 run.py data     # fetch and process data only
python3 run.py train    # train model only
```

### Start API Server
```bash
cd backend
source .venv/bin/activate
python3 api/main.py      # Starts on http://localhost:8000
```

### Start Frontend
```bash
cd frontend
npm install
npm run dev             # Starts on http://localhost:5173
```

Or run steps individually:

1. `python3 src/fetch_pro_matches.py` — pull match metadata
2. `python3 src/fetch_pro_players.py` — pull player roles
3. `python3 src/collect_player_data.py` — pull rosters
4. `python3 src/build_datasets.py` — build csvs
5. `python3 src/compute_glicko.py` — build ratings
6. `python3 src/train.py` — train model

## API Endpoints

### Core Prediction
- `POST /predict` - Predict match outcome given 5v5 account IDs
- `GET /players` - Get all rated players with Glicko ratings

### Upcoming & Live Matches
- `GET /upcoming` - Upcoming matches from Liquipedia (with roster resolution)
- `GET /live` - Currently running matches from PandaScore

### Match History
- `GET /matches` - Paginated historical matches
- `GET /matches/{id}` - Detailed match with player rosters and ratings

## Data Sources

### Training & Ratings
- **OpenDota API**: Historical match data (~3,926 pro matches)
- Player-level Glicko-1 ratings computed chronologically
- Schedule fatigue features (rest days, recent match load)

### Live Integration
- **Liquipedia API**: Upcoming match schedules (free, no auth)
- **Liquipedia Web Scraping**: Team rosters (7-day cache)
- **Player Name Mapping**: Exact + fuzzy matching to OpenDota database
- **PandaScore API**: Live match scores and status

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
Hi Oak Gyi
