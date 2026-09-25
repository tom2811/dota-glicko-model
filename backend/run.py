"""Cross-platform pipeline runner. Use this instead of Makefile on Windows."""
import subprocess, sys, os

PYTHON = sys.executable

STEPS = {
    "data": [
        ("src/fetch_pro_matches.py", "Fetching match metadata"),
        ("src/fetch_pro_players.py", "Fetching player roles"),
        ("src/collect_player_data.py", "Fetching rosters"),
        ("src/build_datasets.py", "Building CSVs"),
        ("src/compute_glicko.py", "Computing Glicko ratings"),
    ],
    "train": [
        ("src/train.py", "Training model"),
    ],
}

def run(targets):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    for target in targets:
        for script, desc in STEPS[target]:
            print(f"\n--- {desc} ---")
            result = subprocess.run([PYTHON, script])
            if result.returncode != 0:
                print(f"FAILED: {script}")
                sys.exit(1)

if __name__ == "__main__":
    args = sys.argv[1:] or ["data", "train"]
    valid = {"data", "train"}
    targets = [a for a in args if a in valid]
    if not targets:
        print(f"Usage: python run.py [data|train]")
        sys.exit(1)
    run(targets)
