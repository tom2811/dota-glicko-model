import requests
import json
import os

def main():
    os.makedirs("data/raw", exist_ok=True)
    print("Fetching /proPlayers...")
    resp = requests.get("https://api.opendota.com/api/proPlayers")
    resp.raise_for_status()
    players = resp.json()
    with open("data/raw/pro_players.json", "w") as f:
        json.dump(players, f)
    print(f"Saved {len(players)} players to data/raw/pro_players.json")

if __name__ == "__main__":
    main()
