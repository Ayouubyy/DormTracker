import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import watch
from state import load_state, save_state


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

    emergency_calls = [call for call in sent if call.get("priority") == 2]
    assert len(emergency_calls) == 1
    emergency = emergency_calls[0]
    assert emergency["priority"] == 2
    assert emergency["retry"] == 60
    assert emergency["expire"] == 10800

    assert load_state(state_path)["last_seen_id"] == 139


def test_new_non_housing_post_only_sends_normal_alert(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    # Recent heartbeat so this test isolates the post-alert behavior without an
    # incidental heartbeat ping also landing in `sent`.
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0})
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

    normal_calls = [call for call in sent if call.get("priority", 0) == 0]
    assert len(normal_calls) == 1
    assert all(call.get("priority") != 2 for call in sent)
    assert load_state(state_path)["last_seen_id"] == 139


def test_heartbeat_sent_when_hour_has_elapsed(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    old_heartbeat = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    save_state(state_path, {"last_seen_id": 139, "last_heartbeat_utc": old_heartbeat, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    # The page still returns its normal (non-empty) listing; there's just nothing
    # newer than what we've already seen (id 139).
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert any("heartbeat" in (k.get("title") or "").lower() for k in sent)
    new_heartbeat = load_state(state_path)["last_heartbeat_utc"]
    assert new_heartbeat != old_heartbeat


def test_heartbeat_not_sent_before_hour_elapses(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    save_state(state_path, {"last_seen_id": 139, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert sent == []
    assert load_state(state_path)["last_heartbeat_utc"] == recent_heartbeat


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


def test_dry_run_never_mutates_state_file(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    original_state = {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 0}
    save_state(state_path, original_state)
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        # A new, housing-related post exists — a real (non-dry-run) run would advance
        # last_seen_id past it. A dry run must leave the persisted state untouched so
        # the very next real cron run still sees this post as new.
        lambda html: [watch.Post(id=139, title="Avis hébergement", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: None)

    watch.run_check("user", "token", dry_run=True)

    assert load_state(state_path) == original_state


def test_dry_run_bootstrap_never_mutates_state_file(tmp_path, monkeypatch):
    # Bootstrap branch (last_seen_id == 0) has its own save_state call site —
    # verify it's guarded the same way as the main path.
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: None)

    watch.run_check("user", "token", dry_run=True)

    assert not state_path.exists()


def test_successful_run_resets_failure_count(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 2})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: None)

    watch.run_check("user", "token")

    assert load_state(state_path)["failure_count"] == 0


def test_empty_parse_result_is_treated_as_a_failure_not_all_clear(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(watch, "parse_latest_posts", lambda html: [])
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    # No heartbeat/all-clear message should have been sent, and this counts as a failure.
    assert sent == []
    assert load_state(state_path)["failure_count"] == 1
    assert load_state(state_path)["last_seen_id"] == 138  # unchanged


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
    assert load_state(state_path)["failure_count"] == 3
    assert load_state(state_path)["last_seen_id"] == 138  # unchanged


def test_main_exits_with_error_when_credentials_missing(monkeypatch, capsys):
    monkeypatch.delenv("PUSHOVER_USER_KEY", raising=False)
    monkeypatch.delenv("PUSHOVER_API_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["watch.py"])

    with pytest.raises(SystemExit) as exc_info:
        watch.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "PUSHOVER_USER_KEY" in captured.err
    assert "PUSHOVER_API_TOKEN" in captured.err
