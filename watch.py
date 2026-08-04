import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scraper import SUPCOM_URL, Post, fetch_html, parse_latest_posts
from keywords import is_housing_related
from state import load_state, save_state
from pushover import send_pushover

STATE_PATH = Path(__file__).parent / "state.json"
HEARTBEAT_INTERVAL = timedelta(hours=1)


def run_check(user_key: str, api_token: str, dry_run: bool = False) -> None:
    state = load_state(STATE_PATH)
    now = datetime.now(timezone.utc)

    try:
        html = fetch_html()
        posts = parse_latest_posts(html)
    except Exception as exc:
        state["failure_count"] = state.get("failure_count", 0) + 1
        print(f"Fetch/parse failed ({state['failure_count']} in a row): {exc}", file=sys.stderr)
        if state["failure_count"] == 3 and not dry_run:
            send_pushover(
                user_key, api_token,
                message=f"The SUP'COM watcher has failed {state['failure_count']} checks in a row: {exc}",
                title="⚠️ SUP'COM watcher error",
                priority=0,
            )
        save_state(STATE_PATH, state)
        return

    state["failure_count"] = 0
    last_seen_id = state["last_seen_id"]

    if last_seen_id == 0:
        if posts:
            state["last_seen_id"] = max(post.id for post in posts)
        save_state(STATE_PATH, state)
        print(f"Bootstrapped state with last_seen_id={state['last_seen_id']}")
        return

    new_posts = sorted((post for post in posts if post.id > last_seen_id), key=lambda post: post.id)

    for post in new_posts:
        message = f"{post.title}\n{post.url}"
        if dry_run:
            print(f"[dry-run] would send normal ping: {message}")
        else:
            send_pushover(user_key, api_token, message=message, title="📰 New SUP'COM post", priority=0)

        if is_housing_related(post.title):
            if dry_run:
                print(f"[dry-run] would send EMERGENCY alert: {message}")
            else:
                send_pushover(
                    user_key, api_token,
                    message=f"HOUSING POST DETECTED:\n{message}",
                    title="🚨 SUP'COM HOUSING ALERT",
                    priority=2,
                    sound="siren",
                    retry=60,
                    expire=10800,
                )

    if new_posts:
        state["last_seen_id"] = max(post.id for post in new_posts)

    last_heartbeat = state.get("last_heartbeat_utc")
    should_heartbeat = last_heartbeat is None or (
        now - datetime.fromisoformat(last_heartbeat) >= HEARTBEAT_INTERVAL
    )

    if should_heartbeat:
        latest_id = state["last_seen_id"]
        if new_posts:
            summary = f"found {len(new_posts)} new post(s) this hour, latest is #{latest_id}."
        else:
            summary = f"no new posts, latest is #{latest_id}."
        heartbeat_message = f"✅ SUP'COM watcher OK — {summary}"

        if dry_run:
            print(f"[dry-run] would send heartbeat: {heartbeat_message}")
        else:
            send_pushover(user_key, api_token, message=heartbeat_message, title="SUP'COM watcher heartbeat", priority=0)

        state["last_heartbeat_utc"] = now.isoformat()

    save_state(STATE_PATH, state)


def send_test_notification(user_key: str, api_token: str, emergency: bool = False) -> None:
    if emergency:
        send_pushover(
            user_key, api_token,
            message="[TEST] This is a fake EMERGENCY alert from the SUP'COM watcher.",
            title="🚨 [TEST] SUP'COM watcher",
            priority=2,
            sound="siren",
            retry=60,
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
