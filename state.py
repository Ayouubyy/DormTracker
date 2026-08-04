import json
from pathlib import Path

DEFAULT_STATE = {
    "last_seen_id": 0,
    "last_heartbeat_utc": None,
    "failure_count": 0,
}


def load_state(path: Path) -> dict:
    if not path.exists():
        return dict(DEFAULT_STATE)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return {**DEFAULT_STATE, **data}


def save_state(path: Path, state: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
