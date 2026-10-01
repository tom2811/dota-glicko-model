# Dota 2 Match Predictor

Predicts professional Dota 2 match outcomes using Glicko player ratings + gradient boosting. Trained on 7,607 pro matches with 2,081 tracked players. Includes web interface for upcoming matches and live scores.

**Stack**: FastAPI + scikit-learn + React + TypeScript

## What It Does

- Tracks individual player skill using Glicko-1 rating system
- Detects team fatigue from match schedules (rest days, recent games)
- Combines Glicko math with gradient boosting for predictions
- Shows live upcoming matches with win probabilities
- ~70% AUC on historical test data

## Quick Start

**Requirements**: Python 3.9+, Node.js 16+

**Backend**:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python api/main.py  # runs on :8000
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev  # runs on :5173
```

**Config**: Copy `.env.example` to `.env` in both directories. PandaScore API key optional (for live match scores).

### Refreshing Data (Optional)

Pre-trained model included. To retrain with fresh OpenDota data:

```bash
cd backend
python run.py  # takes several hours due to rate limiting
```

**Note**: OpenDota has daily rate limits - full data pull requires multiple days. Processed data already committed, so this is optional.

## API

- `POST /predict` - Get win probability for 5v5 player matchup
- `GET /upcoming` - Upcoming matches from Liquipedia (with rosters)
- `GET /live` - Currently running matches from PandaScore
- `GET /matches` - Historical match data (paginated)
- `GET /matches/{id}` - Match details with player rosters
- `GET /players` - All players with Glicko ratings

## How It Works

Uses a two-stage approach:
1. Glicko-1 computes individual player ratings chronologically
2. Gradient boosting learns schedule adjustments (fatigue, recent match load)

Custom `GlickoInit` estimator forces the model to start from pure Glicko probability, then trees learn corrections from role composition and schedule features.

**Key features**:
- Core/support rating differentials (position 1-3 vs 4-5)
- Rest days and match frequency (last 7 days)
- Glicko win probability (baseline)

**Performance** (7,607 matches, 80/20 time split):
- Test AUC: 0.7031
- Test Log Loss: 0.6280
- Glicko baseline: 0.639 Log Loss

Match coverage: 60-80% tier 1, 30-50% tier 2 (only predict with complete rosters).

## Data Sources

**Training**: [OpenDota API](https://docs.opendota.com/) - 7,607 pro matches, 2,081 players (no auth needed)

**Live**:
- [Liquipedia API](https://dota.haglund.dev) - upcoming match schedules
- [OpenDota API](https://docs.opendota.com/) - team rosters (7-day cache)
- [PandaScore API](https://pandascore.co/) - live scores (requires key)

**Roster matching**: Liquipedia team name → OpenDota team ID → player account_ids → validate against Glicko database. Only show predictions for complete 5v5 rosters with ratings.

## Project Structure

```
backend/
  api/main.py          # FastAPI endpoints
  src/                 # Pipeline: fetch → process → train
  data/processed/      # CSVs (committed)
  models/              # model.pkl + ratings (committed)
  
frontend/
  src/App.tsx          # React UI (hash routing, no react-router)
```

---

Data: [OpenDota](https://www.opendota.com/) · [Liquipedia](https://liquipedia.net/dota2/) · [PandaScore](https://pandascore.co/)