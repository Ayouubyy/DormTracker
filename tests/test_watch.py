import sys
from datetime import datetime, timedelta, timezone

import pytest

import watch
from pushover import PushoverError
from state import load_state, save_state


def test_bootstrap_run_seeds_state_without_sending_alerts(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append((a, k)))

    watch.run_check("user", "token")

    assert sent == []
    assert load_state(state_path)["last_seen_id"] == 139
    # First-ever observation of the registration-link field must also seed silently.
    assert load_state(state_path)["registration_link_active"] is False


def test_new_housing_post_triggers_normal_and_emergency_alerts(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [
            watch.Post(id=139, title="Avis hébergement 2026/2027", url="https://www.supcom.tn/details_actualite/139"),
        ],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
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
    assert emergency["retry"] == 30
    assert emergency["expire"] == 10800

    assert load_state(state_path)["last_seen_id"] == 139


def test_new_non_housing_post_only_sends_normal_alert(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    # Recent heartbeat so this test isolates the post-alert behavior without an
    # incidental heartbeat ping also landing in `sent`.
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [
            watch.Post(id=139, title="Fête de fin d'année", url="https://www.supcom.tn/details_actualite/139"),
        ],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
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
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    # The page still returns its normal (non-empty) listing; there's just nothing
    # newer than what we've already seen (id 139).
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
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
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert sent == []
    assert load_state(state_path)["last_heartbeat_utc"] == recent_heartbeat


def test_dry_run_never_calls_send_pushover(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Avis hébergement", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
    called = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: called.append(k))

    watch.run_check("user", "token", dry_run=True)

    assert called == []


def test_dry_run_never_mutates_state_file(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 0})
    # Read back through load_state (not the raw dict passed to save_state) so this
    # assertion doesn't hardcode DEFAULT_STATE's exact key set — it just needs to prove
    # nothing changed, whatever fields the state file happens to carry.
    original_state = load_state(state_path)
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        # A new, housing-related post exists — a real (non-dry-run) run would advance
        # last_seen_id past it. A dry run must leave the persisted state untouched so
        # the very next real cron run still sees this post as new.
        lambda html: [watch.Post(id=139, title="Avis hébergement", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: None)

    watch.run_check("user", "token", dry_run=True)

    assert load_state(state_path) == original_state


def test_dry_run_bootstrap_never_mutates_state_file(tmp_path, monkeypatch):
    # Bootstrap branch (last_seen_id == 0) has its own save_state call site —
    # verify it's guarded the same way as the main path.
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: None)

    watch.run_check("user", "token", dry_run=True)

    assert not state_path.exists()


def test_successful_run_resets_failure_count(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": None, "failure_count": 2})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: None)

    watch.run_check("user", "token")

    assert load_state(state_path)["failure_count"] == 0


def test_empty_parse_result_is_treated_as_a_failure_not_all_clear(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    # Recent heartbeat so this test isolates the "no all-clear on failure" behavior
    # without the failure path's own degraded heartbeat also landing in `sent`.
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
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
    # Recent heartbeat so the only message we expect here is the one-time failure alert.
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 2})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)

    def boom():
        raise RuntimeError("site is down")

    monkeypatch.setattr(watch, "fetch_html", boom)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert len(sent) == 1
    assert "failed 3 checks in a row" in sent[0]["message"]
    assert load_state(state_path)["failure_count"] == 3
    assert load_state(state_path)["last_seen_id"] == 138  # unchanged


def test_failure_path_still_sends_a_degraded_heartbeat_after_the_one_time_alert(tmp_path, monkeypatch):
    # The regression this guards: the failure branch used to `return` before ever
    # reaching the heartbeat block, so past the single failure_count==3 alert a durable
    # outage went permanently and undetectably silent. A silent phone must never be
    # mistakable for "everything's fine".
    state_path = tmp_path / "state.json"
    old_heartbeat = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": old_heartbeat, "failure_count": 7})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)

    def boom():
        raise RuntimeError("site is down")

    monkeypatch.setattr(watch, "fetch_html", boom)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    # Well past failure_count==3, so the one-time alert is long gone — but a degraded
    # heartbeat must still go out.
    assert len(sent) == 1
    assert "DEGRADED" in sent[0]["message"]
    assert "8 consecutive failures" in sent[0]["message"]
    assert load_state(state_path)["failure_count"] == 8
    # And the heartbeat clock advanced, so it won't re-fire for another hour.
    assert load_state(state_path)["last_heartbeat_utc"] != old_heartbeat


def test_failure_path_does_not_spam_heartbeats_every_five_minutes(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 7})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)

    def boom():
        raise RuntimeError("site is down")

    monkeypatch.setattr(watch, "fetch_html", boom)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert sent == []
    assert load_state(state_path)["last_heartbeat_utc"] == recent_heartbeat


def test_degraded_heartbeat_repeats_hourly_across_a_prolonged_outage(tmp_path, monkeypatch):
    """Six hours of 5-minute failing checks must produce ~one message per hour, not one total."""
    state_path = tmp_path / "state.json"
    start = datetime.now(timezone.utc) - timedelta(hours=6)
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": start.isoformat(), "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)

    def boom():
        raise RuntimeError("site is down")

    monkeypatch.setattr(watch, "fetch_html", boom)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    # Simulate 72 consecutive failing 5-minute checks (6 hours) by advancing "now".
    class FakeDatetime(datetime):
        current = start

        @classmethod
        def now(cls, tz=None):
            return cls.current

    monkeypatch.setattr(watch, "datetime", FakeDatetime)

    for tick in range(1, 73):
        FakeDatetime.current = start + timedelta(minutes=5 * tick)
        watch.run_check("user", "token")

    degraded = [k for k in sent if "DEGRADED" in k["message"]]
    # One degraded heartbeat per elapsed hour — never silent for longer than that, and
    # never spamming on every 5-minute check either.
    assert len(degraded) == 6, [k["message"] for k in sent]
    # Plus exactly the one historical failure heads-up at failure_count == 3.
    assert len([k for k in sent if "failed 3 checks in a row" in k["message"]]) == 1
    assert load_state(state_path)["failure_count"] == 72


def test_emergency_alert_still_sent_when_normal_ping_fails(tmp_path, monkeypatch):
    # The regression this guards: the normal ping used to be sent first, unguarded, so a
    # PushoverError there aborted run_check before the housing siren was ever attempted —
    # losing the single most important message in the system to the least important one.
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [
            watch.Post(id=139, title="Avis hébergement 2026/2027", url="https://www.supcom.tn/details_actualite/139"),
        ],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")

    sent = []

    def flaky_send(*args, **kwargs):
        if kwargs.get("priority", 0) != 2:
            raise PushoverError("normal ping exploded")
        sent.append(kwargs)

    monkeypatch.setattr(watch, "send_pushover", flaky_send)

    watch.run_check("user", "token")

    assert len(sent) == 1
    assert sent[0]["priority"] == 2
    assert "HOUSING POST DETECTED" in sent[0]["message"]
    # The normal ping never landed, so don't advance past this post — the next check
    # retries it rather than silently dropping the notification.
    assert load_state(state_path)["last_seen_id"] == 138


def test_normal_ping_still_sent_when_emergency_alert_fails(tmp_path, monkeypatch):
    # Symmetric guard: neither send may be able to skip the other.
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {"last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0})
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [
            watch.Post(id=139, title="Avis hébergement 2026/2027", url="https://www.supcom.tn/details_actualite/139"),
        ],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: "<html></html>")

    sent = []

    def flaky_send(*args, **kwargs):
        if kwargs.get("priority", 0) == 2:
            raise PushoverError("siren exploded")
        sent.append(kwargs)

    monkeypatch.setattr(watch, "send_pushover", flaky_send)

    watch.run_check("user", "token")

    assert len(sent) == 1
    assert sent[0]["priority"] == 0
    assert load_state(state_path)["last_seen_id"] == 138


# Real markup captured from https://www.supcom.tn/details_actualite/136 (placeholder,
# not yet open) and .../90 (last year's equivalent post, after registration opened) —
# see link_watch.py and tests/test_link_watch.py for the full detection logic these
# exercise end-to-end through run_check.
_LINK_INACTIVE_HTML = "(مع احترام مواعيد التسجيل : الرابط)."
_LINK_ACTIVE_HTML = (
    '(مع احترام مواعيد التسجيل : <a href="https://edx.supcom.tn/public/short.faces?l=X">الرابط</a>).'
)


def test_registration_link_activation_triggers_emergency_alert(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {
        "last_seen_id": 139, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0,
        "registration_link_active": False,
    })
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: _LINK_ACTIVE_HTML)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert len(sent) == 1
    assert sent[0]["priority"] == 2
    assert sent[0]["sound"] == "siren"
    assert sent[0]["retry"] == 30
    assert sent[0]["expire"] == 10800
    assert "supcom.tn/details_actualite/136" in sent[0]["message"]
    assert load_state(state_path)["registration_link_active"] is True


def test_registration_link_already_active_does_not_resend_alert(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {
        "last_seen_id": 139, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0,
        "registration_link_active": True,
    })
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: _LINK_ACTIVE_HTML)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert sent == []
    assert load_state(state_path)["registration_link_active"] is True


def test_registration_link_send_failure_leaves_state_false_for_retry(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {
        "last_seen_id": 139, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0,
        "registration_link_active": False,
    })
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: _LINK_ACTIVE_HTML)

    def boom_send(*args, **kwargs):
        raise PushoverError("siren exploded")

    monkeypatch.setattr(watch, "send_pushover", boom_send)

    watch.run_check("user", "token")

    # The alert never landed — the next check must see this as still-inactive and retry,
    # not silently mark it "seen" and go quiet on the single most important message here.
    assert load_state(state_path)["registration_link_active"] is False


def test_watched_post_fetch_failure_counts_as_a_failure(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {
        "last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0,
        "registration_link_active": False,
    })
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )

    def boom():
        raise RuntimeError("watched post page is down")

    monkeypatch.setattr(watch, "fetch_watched_post_html", boom)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    # Folded into the same failure machinery as the main feed fetch — not the 3rd
    # failure yet, so no alert, but the count must still advance and nothing else
    # (last_seen_id, registration_link_active) may change on a failed check.
    assert sent == []
    assert load_state(state_path)["failure_count"] == 1
    assert load_state(state_path)["last_seen_id"] == 138
    assert load_state(state_path)["registration_link_active"] is False


def test_supcom_site_up_flip_triggers_emergency_alert(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {
        "last_seen_id": 139, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0,
        "registration_link_active": False, "supcom_site_up": False, "inscription_site_up": False,
    })
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: False)  # inscription.tn stays down
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")  # supcom.tn's fetch succeeds now
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: _LINK_INACTIVE_HTML)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert len(sent) == 1
    assert sent[0]["priority"] == 2
    assert "supcom.tn" in sent[0]["message"]
    assert load_state(state_path)["supcom_site_up"] is True


def test_inscription_site_up_flip_triggers_emergency_alert(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {
        "last_seen_id": 139, "last_heartbeat_utc": recent_heartbeat, "failure_count": 0,
        "registration_link_active": False, "supcom_site_up": True, "inscription_site_up": False,
    })
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: True)  # inscription.tn just came back
    monkeypatch.setattr(watch, "fetch_html", lambda: "<html></html>")
    monkeypatch.setattr(
        watch, "parse_latest_posts",
        lambda html: [watch.Post(id=139, title="Post-Doc call", url="https://www.supcom.tn/details_actualite/139")],
    )
    monkeypatch.setattr(watch, "fetch_watched_post_html", lambda: _LINK_INACTIVE_HTML)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    assert len(sent) == 1
    assert sent[0]["priority"] == 2
    assert "inscription.tn" in sent[0]["message"]
    assert load_state(state_path)["inscription_site_up"] is True


def test_inscription_check_still_runs_during_a_supcom_outage(tmp_path, monkeypatch):
    # This is the entire point of checking it unconditionally: a supcom.tn outage must
    # never block detecting inscription.tn coming back online in the meantime.
    state_path = tmp_path / "state.json"
    recent_heartbeat = datetime.now(timezone.utc).isoformat()
    save_state(state_path, {
        "last_seen_id": 138, "last_heartbeat_utc": recent_heartbeat, "failure_count": 5,
        "registration_link_active": False, "supcom_site_up": False, "inscription_site_up": False,
    })
    monkeypatch.setattr(watch, "STATE_PATH", state_path)
    monkeypatch.setattr(watch, "is_site_up", lambda url: True)  # inscription.tn is back

    def boom():
        raise RuntimeError("supcom.tn is still down")

    monkeypatch.setattr(watch, "fetch_html", boom)
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    watch.run_check("user", "token")

    inscription_alerts = [k for k in sent if "inscription.tn" in k.get("message", "")]
    assert len(inscription_alerts) == 1
    assert inscription_alerts[0]["priority"] == 2
    assert load_state(state_path)["inscription_site_up"] is True
    # supcom.tn's own state must still correctly reflect "still down" — unaffected.
    assert load_state(state_path)["supcom_site_up"] is False


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


def test_main_rejects_emergency_without_test_notify(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["watch.py", "--emergency"])

    with pytest.raises(SystemExit) as exc_info:
        watch.main()

    assert exc_info.value.code == 2
    assert "--emergency" in capsys.readouterr().err


def test_main_rejects_test_notify_combined_with_dry_run(monkeypatch, capsys):
    # --dry-run promises nothing real is ever sent; --test-notify's whole job is to send
    # something real. The combination used to quietly send a real push anyway.
    monkeypatch.setattr(sys, "argv", ["watch.py", "--dry-run", "--test-notify"])
    sent = []
    monkeypatch.setattr(watch, "send_pushover", lambda *a, **k: sent.append(k))

    with pytest.raises(SystemExit) as exc_info:
        watch.main()

    assert exc_info.value.code == 2
    assert sent == []
