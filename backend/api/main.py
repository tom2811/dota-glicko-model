import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import os
import sys

# Add src to python path to load the custom GlickoInit class
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.train import GlickoInit

app = FastAPI(title="Dota 2 Glicko API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to hold model and state
model = None

@app.on_event("startup")
def load_model():
    global model
    model_path = os.path.join(os.path.dirname(__file__), "..", "models", "model.pkl")
    if os.path.exists(model_path):
        model = joblib.load(model_path)
    else:
        print(f"Warning: Model not found at {model_path}. Run train.py first.")

class MatchupRequest(BaseModel):
    radiant_account_ids: list[int]
    dire_account_ids: list[int]

@app.get("/")
def read_root():
    return {"status": "healthy", "model_loaded": model is not None}

@app.post("/predict")
def predict_match(req: MatchupRequest):
    if not model:
        raise HTTPException(status_code=503, detail="Model is not loaded")
    
    if len(req.radiant_account_ids) != 5 or len(req.dire_account_ids) != 5:
        raise HTTPException(status_code=400, detail="Must provide exactly 5 players per team")

    # TODO: Implement feature construction from account_ids using the latest_glicko.csv and latest_players.csv
    # For now, return a placeholder prediction
    return {
        "radiant_win_prob": 0.5,
        "message": "Feature engineering from account IDs coming soon in M6 phase 2"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
