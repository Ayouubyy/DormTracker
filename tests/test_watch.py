from datetime import datetime, timedelta, timezone
from pathlib import Path

import watch
from state import save_state


def test_bootstrap_run_seeds_state_without_sending_alerts(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append((a, k)))

    watch.run_check("user", "token")

    assert sent == []
    from state import load_state
    assert load_state(state_path)["last_seen_id"] == 139


def test_new_housing_post_triggers_normal_and_emergency_alerts(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [
            watch.Post(id=139, title="Avis hébergement 2026/2027", url="https://www.supcom.tn/details_actualite/139"),
        ],
    )
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    priorities = [call.get("priority", 0) for call in sent]
    assert 0 in priorities  # normal ping
    assert 2 in priorities  # emergency alert
    from state import load_state
    assert load_state(state_path)["last_seen_id"] == 139


def test_new_non_housing_post_only_sends_normal_alert(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [
            watch.Post(id=139, title="Fête de fin d'année", url="https://www.supcom.tn/details_actualite/139"),
        ],
    )
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    priorities = [call.get("priority", 0) for call in sent]
    assert 2 not in priorities


def test_heartbeat_sent_when_hour_has_elapsed(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    old_heartbeat = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    save_state(state_path, {"last_seen_id": 139, "last_heartbeat_utc": old_heartbeat, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(watch, "parse_latest_posts", lambda html: [])
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert any("heartbeat" in (k.get("title") or "").lower() for k in sent)


def test_heartbeat_not_sent_before_hour_elapses(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    save_state(state_path, {"last_seen_id": 139, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(watch, "parse_latest_posts", lambda html: [])
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert sent == []


def test_dry_run_never_calls_send_pushover(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Avis hébergement", url="https://www.supcom.tn/details_actualite/139")],
    )
    called = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: called.append(k))

    watch.run_check("user", "token", dry_run=True)

    assert called == []


def test_third_consecutive_failure_sends_error_alert(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 2})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)

    def boom():
        raise RuntimeError("site is down")

    monkeypatch.setattr(watch, "fetch_html", boom)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert len(sent) == 1
    from state import load_state
    assert load_state(state_path)["failure_count"] == 3
    assert load_state(state_path)["last_seen_id"] == 138  # unchanged
