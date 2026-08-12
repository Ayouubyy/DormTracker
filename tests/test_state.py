import json

from state import DEFAULT_STATE, load_state, save_state


def test_load_state_returns_defaults_when_file_missing(tmp_path):
    path = tmp_path / "state.json"

    state = load_state(path)

    assert state == DEFAULT_STATE


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "state.json"
    original = {
        "last_seen_id": 139,
        "last_heartbeat_utc": "2026-08-04T12:00:00+00:00",
        "failure_count": 0,
        "registration_link_active": True,
        "supcom_site_up": True,
        "inscription_site_up": False,
    }

    save_state(path, original)
    loaded = load_state(path)

    assert loaded == original


def test_load_state_fills_missing_keys_with_defaults(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"last_seen_id": 5}), encoding="utf-8")

    state = load_state(path)

    assert state == {
        "last_seen_id": 5,
        "last_heartbeat_utc": None,
        "failure_count": 0,
        "registration_link_active": None,
        "supcom_site_up": None,
        "inscription_site_up": None,
    }
