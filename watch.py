import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scraper import Post, fetch_html, parse_latest_posts
from keywords import is_housing_related
from state import load_state, save_state
from pushover import PushoverError, send_pushover

STATE_PATH = Path(__file__).parent / "state.json"
HEARTBEAT_INTERVAL = timedelta(hours=1)


def _notify(user_key: str, api_token: str, dry_run: bool, label: str, **kwargs) -> None:
    """Send one Pushover message, or just print it under --dry-run.

    Raises PushoverError on delivery failure (never under dry_run) so callers can
    decide per-message whether a failure is fatal.
    """
    if dry_run:
        print(f"[dry-run] would send {label}: {kwargs['message']}")
        return
    send_pushover(user_key, api_token, **kwargs)


def _heartbeat_due(state: dict, now: datetime) -> bool:
    last_heartbeat = state["last_heartbeat_utc"]
    return last_heartbeat is None or (
        now - datetime.fromisoformat(last_heartbeat) >= HEARTBEAT_INTERVAL
    )


def _handle_failure(
    state: dict,
    now: datetime,
    exc: Exception,
    user_key: str,
    api_token: str,
    dry_run: bool,
) -> None:
    """Account for one fetch/parse failure and make sure the phone still hears from us.

    Two independent signals live here:

    1. A one-time heads-up at exactly the 3rd consecutive failure.
    2. A *degraded* heartbeat on the same hourly cadence as the healthy path. Without
       this, a durable failure (site redesign, network block, long outage) would send
       that single heads-up and then go permanently silent — and a silent phone is
       indistinguishable from "everything's fine", which defeats the whole point of
       having a heartbeat at all.
    """
    state["failure_count"] += 1
    failure_count = state["failure_count"]
    print(f"Fetch/parse failed ({failure_count} in a row): {exc}", file=sys.stderr)

    if failure_count == 3:
        try:
            _notify(
                user_key, api_token, dry_run, "failure alert",
                message=f"The SUP'COM watcher has failed {failure_count} checks in a row: {exc}",
                title="⚠️ SUP'COM watcher error",
                priority=0,
            )
        except PushoverError as send_exc:
            print(f"Failure alert could not be sent: {send_exc}", file=sys.stderr)

    if _heartbeat_due(state, now):
        try:
            _notify(
                user_key, api_token, dry_run, "degraded heartbeat",
                message=(
                    f"⚠️ SUP'COM watcher DEGRADED — {failure_count} consecutive failures, "
                    "last success unknown"
                ),
                title="SUP'COM watcher heartbeat",
                priority=0,
            )
        except PushoverError as send_exc:
            print(f"Degraded heartbeat could not be sent: {send_exc}", file=sys.stderr)
        else:
            # Only mark the heartbeat as delivered if it actually was, so a transient
            # Pushover outage doesn't cost us a whole hour of silence.
            state["last_heartbeat_utc"] = now.isoformat()


def run_check(user_key: str, api_token: str, dry_run: bool = False) -> None:
    state = load_state(STATE_PATH)
    now = datetime.now(timezone.utc)

    try:
        html = fetch_html()
        posts = parse_latest_posts(html)
        if not posts:
            raise RuntimeError("parsed zero posts — site markup may have changed")
    except Exception as exc:
        _handle_failure(state, now, exc, user_key, api_token, dry_run)
        if not dry_run:
            save_state(STATE_PATH, state)
        return

    state["failure_count"] = 0
    last_seen_id = state["last_seen_id"]

    if last_seen_id == 0:
        state["last_seen_id"] = max(post.id for post in posts)
        if not dry_run:
            save_state(STATE_PATH, state)
        print(f"Bootstrapped state with last_seen_id={state['last_seen_id']}")
        return

    new_posts = sorted((post for post in posts if post.id > last_seen_id), key=lambda post: post.id)

    delivery_failed = False
    for post in new_posts:
        message = f"{post.title}\n{post.url}"

        # The emergency siren goes FIRST, deliberately: in a first-come-first-served
        # dorm race it is the single most important message this system will ever send,
        # and it must never be gated on the lower-priority ping succeeding. Each send is
        # also individually guarded so neither one failing can skip the other.
        if is_housing_related(post.title):
            try:
                _notify(
                    user_key, api_token, dry_run, "EMERGENCY alert",
                    message=f"HOUSING POST DETECTED:\n{message}",
                    title="🚨 SUP'COM HOUSING ALERT",
                    priority=2,
                    sound="siren",
                    retry=30,
                    expire=10800,
                )
            except PushoverError as exc:
                delivery_failed = True
                print(f"EMERGENCY alert for post #{post.id} failed: {exc}", file=sys.stderr)

        try:
            _notify(
                user_key, api_token, dry_run, "normal ping",
                message=message, title="📰 New SUP'COM post", priority=0,
            )
        except PushoverError as exc:
            delivery_failed = True
            print(f"Normal ping for post #{post.id} failed: {exc}", file=sys.stderr)

    if new_posts:
        if delivery_failed:
            # Leave last_seen_id where it is so the next run treats these posts as new
            # again and retries. A duplicate ping is a nuisance; a missed housing siren
            # is the failure this whole project exists to prevent.
            print(
                "At least one alert failed to send — leaving last_seen_id unchanged so "
                "the next check retries these posts.",
                file=sys.stderr,
            )
        else:
            state["last_seen_id"] = max(post.id for post in new_posts)

    if _heartbeat_due(state, now):
        latest_id = state["last_seen_id"]
        if new_posts:
            summary = f"found {len(new_posts)} new post(s) in this check, latest is #{latest_id}."
        else:
            summary = f"no new posts, latest is #{latest_id}."
        heartbeat_message = f"✅ SUP'COM watcher OK — {summary}"

        try:
            _notify(
                user_key, api_token, dry_run, "heartbeat",
                message=heartbeat_message,
                title="SUP'COM watcher heartbeat",
                priority=0,
            )
        except PushoverError as exc:
            print(f"Heartbeat could not be sent: {exc}", file=sys.stderr)
        else:
            state["last_heartbeat_utc"] = now.isoformat()

    if not dry_run:
        save_state(STATE_PATH, state)


def send_test_notification(user_key: str, api_token: str, emergency: bool = False) -> None:
    if emergency:
        send_pushover(
            user_key, api_token,
            message="[TEST] This is a fake EMERGENCY alert from the SUP'COM watcher.",
            title="🚨 [TEST] SUP'COM watcher",
            priority=2,
            sound="siren",
            retry=30,
            expire=10800,
        )
        print("Sent test EMERGENCY notification.")
    else:
        send_pushover(
            user_key, api_token,
            message="[TEST] This is a fake notification from the SUP'COM watcher.",
            title="[TEST] SUP'COM watcher",
            priority=0,
        )
        print("Sent test normal notification.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SUP'COM dorm announcement watcher")
    parser.add_argument("--dry-run", action="store_true", help="Run the real check but only print what would be sent")
    parser.add_argument("--test-notify", action="store_true", help="Send one real fake test notification and exit")
    parser.add_argument("--emergency", action="store_true", help="With --test-notify, send it at emergency priority")
    args = parser.parse_args()

    if args.emergency and not args.test_notify:
        parser.error("--emergency only means something together with --test-notify")
    if args.test_notify and args.dry_run:
        # --test-notify's whole job is to send a real push; --dry-run's whole contract is
        # that nothing real is ever sent. Refuse rather than quietly honour one of them.
        parser.error("--test-notify sends a real notification, so it cannot be combined with --dry-run")

    user_key = os.environ.get("PUSHOVER_USER_KEY")
    api_token = os.environ.get("PUSHOVER_API_TOKEN")
    if not user_key or not api_token:
        print("Missing PUSHOVER_USER_KEY / PUSHOVER_API_TOKEN environment variables", file=sys.stderr)
        sys.exit(1)

    if args.test_notify:
        send_test_notification(user_key, api_token, emergency=args.emergency)
        return

    run_check(user_key, api_token, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
