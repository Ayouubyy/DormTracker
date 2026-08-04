# SUP'COM Dorm Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script + GitHub Actions cron workflow that watches supcom.tn's news feed and sends a loud, repeating Pushover alert the moment a housing/dorm-related post appears, plus a quiet hourly heartbeat and a way to send fake test notifications.

**Architecture:** A single small Python package (no framework) with four focused modules (`scraper.py`, `keywords.py`, `state.py`, `pushover.py`) and one orchestrator (`watch.py`) that a GitHub Actions workflow runs every 5 minutes, committing `state.json` back to the repo after each run.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4`, `pytest`, GitHub Actions.

## Global Constraints

- The site (`https://www.supcom.tn/`) is server-rendered plain HTML — no headless browser, no JS execution needed.
- News item DOM shape (confirmed live, do not deviate): each post is `div.course-item` containing `h5.mb-3 > a[href*="/details_actualite/<id>"]` for the title+link.
- Pushover credentials (`PUSHOVER_USER_KEY`, `PUSHOVER_API_TOKEN`) are read only from environment variables, sourced from GitHub Actions encrypted secrets — never hardcoded, never committed.
- Emergency priority Pushover calls use `priority=2`, `retry=60`, `expire=10800` (repeats every 60s for up to 3h).
- `state.json` fields: `last_seen_id` (int), `last_heartbeat_utc` (ISO 8601 string or `null`), `failure_count` (int).
- First-ever run must bootstrap `last_seen_id` silently (no Pushover calls for pre-existing posts).
- Heartbeat fires once per 60 minutes of wall-clock time, piggybacked on the 5-minute cron (no second schedule).
- After 3 consecutive fetch/parse failures, send one low-priority Pushover heads-up before continuing to retry.
- Housing keywords (French + Arabic), case-insensitive substring match on the post title: `hébergement`, `hebergement`, `logement`, `cité universitaire`, `cite universitaire`, `résidence`, `residence`, `internat`, `chambre`, `سكن`, `مبيت`, `الإقامة`, `دار الطالب`.

---

### Task 1: Scraper module — fetch and parse the news feed

**Files:**
- Create: `scraper.py`
- Create: `requirements.txt`
- Create: `tests/fixtures/homepage_sample.html`
- Test: `tests/test_scraper.py`

**Interfaces:**
- Produces: `scraper.SUPCOM_URL: str`, `scraper.Post` (dataclass with fields `id: int`, `title: str`, `url: str`), `scraper.fetch_html(url: str = SUPCOM_URL, timeout: int = 15) -> str`, `scraper.parse_latest_posts(html: str) -> list[Post]` (returns posts in whatever order they appear in the HTML, newest first, as the live site does).

- [ ] **Step 1: Create `requirements.txt`**

```
requests==2.32.3
beautifulsoup4==4.12.3
pytest==8.3.3
```

- [ ] **Step 2: Create the HTML fixture from real captured site markup**

Create `tests/fixtures/homepage_sample.html`:

```html
<div class="my-shuffle-container">
  <div class="grid-item shuffle-item">
    <div class="course-item">
      <div class="coures-img">
        <a href="https://www.supcom.tn/details_actualite/139"><img class="img-fluid" src="x.png" alt=""></a>
        <div class="course-tag"><a href="https://www.supcom.tn/details_actualite/139"><i class="fa fa-calendar"></i> Publiée le :24-07-2026</a></div>
      </div>
      <div class="course-conten">
        <h5 class="mb-3"><a href="https://www.supcom.tn/details_actualite/139">Appel à candidature pour le recrutement d'un(e) chercheur(se) Post-Doc 2026/2027</a></h5>
        <a href="https://www.supcom.tn/details_actualite/139" class="course-author d-flex align-items-center mb-3"><span class="author-name lenght_text"></span></a>
      </div>
    </div>
  </div>
  <div class="grid-item shuffle-item">
    <div class="course-item">
      <div class="coures-img">
        <a href="https://www.supcom.tn/details_actualite/138"><img class="img-fluid" src="x.jpg" alt=""></a>
        <div class="course-tag"><a href="https://www.supcom.tn/details_actualite/138"><i class="fa fa-calendar"></i> Publiée le :22-07-2026</a></div>
      </div>
      <div class="course-conten">
        <h5 class="mb-3"><a href="https://www.supcom.tn/details_actualite/138">Avis concernant l'inscription universitaire et l'hébergement pour l'année universitaire 2026/2027</a></h5>
        <a href="https://www.supcom.tn/details_actualite/138" class="course-author d-flex align-items-center mb-3"><span class="author-name lenght_text"></span></a>
      </div>
    </div>
  </div>
  <div class="grid-item shuffle-item">
    <div class="course-item">
      <div class="coures-img">
        <a href="https://www.supcom.tn/details_actualite/136"><img class="img-fluid" src="x.jpg" alt=""></a>
        <div class="course-tag"><a href="https://www.supcom.tn/details_actualite/136"><i class="fa fa-calendar"></i> Publiée le :22-07-2026</a></div>
      </div>
      <div class="course-conten">
        <h5 class="mb-3"><a href="https://www.supcom.tn/details_actualite/136">2027/2026 بلاغ حول التسجيل الجامعي وبالمبيت بعنوان السنة الجامعية</a></h5>
        <a href="https://www.supcom.tn/details_actualite/136" class="course-author d-flex align-items-center mb-3"><span class="author-name lenght_text"></span></a>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_scraper.py`:

```python
from pathlib import Path

from scraper import parse_latest_posts, Post

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_latest_posts_extracts_id_title_url():
    html = (FIXTURES / "homepage_sample.html").read_text(encoding="utf-8")

    posts = parse_latest_posts(html)

    assert posts == [
        Post(
            id=139,
            title="Appel à candidature pour le recrutement d'un(e) chercheur(se) Post-Doc 2026/2027",
            url="https://www.supcom.tn/details_actualite/139",
        ),
        Post(
            id=138,
            title="Avis concernant l'inscription universitaire et l'hébergement pour l'année universitaire 2026/2027",
            url="https://www.supcom.tn/details_actualite/138",
        ),
        Post(
            id=136,
            title="2027/2026 بلاغ حول التسجيل الجامعي وبالمبيت بعنوان السنة الجامعية",
            url="https://www.supcom.tn/details_actualite/136",
        ),
    ]


def test_parse_latest_posts_returns_empty_list_for_no_matches():
    assert parse_latest_posts("<html><body>nothing here</body></html>") == []
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pip install -r requirements.txt && pytest tests/test_scraper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 5: Implement `scraper.py`**

```python
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

SUPCOM_URL = "https://www.supcom.tn/"

_ID_PATTERN = re.compile(r"/details_actualite/(\d+)")


@dataclass
class Post:
    id: int
    title: str
    url: str


def fetch_html(url: str = SUPCOM_URL, timeout: int = 15) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_latest_posts(html: str) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[Post] = []

    for item in soup.select("div.course-item"):
        link = item.select_one("h5.mb-3 a[href]")
        if link is None:
            continue

        href = link["href"]
        match = _ID_PATTERN.search(href)
        if not match:
            continue

        posts.append(
            Post(
                id=int(match.group(1)),
                title=link.get_text(strip=True),
                url=href,
            )
        )

    return posts
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt scraper.py tests/test_scraper.py tests/fixtures/homepage_sample.html
git commit -m "Add scraper module to fetch and parse SUP'COM news feed"
```

---

### Task 2: Keyword matching module

**Files:**
- Create: `keywords.py`
- Test: `tests/test_keywords.py`

**Interfaces:**
- Consumes: nothing from other modules.
- Produces: `keywords.HOUSING_KEYWORDS: list[str]`, `keywords.is_housing_related(title: str) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_keywords.py`:

```python
from keywords import is_housing_related


def test_matches_french_hebergement_with_accent():
    title = "Avis concernant l'inscription universitaire et l'hébergement pour l'année universitaire 2026/2027"
    assert is_housing_related(title) is True


def test_matches_arabic_mabit():
    title = "2027/2026 بلاغ حول التسجيل الجامعي وبالمبيت بعنوان السنة الجامعية"
    assert is_housing_related(title) is True


def test_matches_is_case_insensitive():
    assert is_housing_related("HÉBERGEMENT étudiant ouvert") is True


def test_does_not_match_unrelated_title():
    title = "Fierté et Excellence : Enactus SUP'COM est Champion de Tunisie !"
    assert is_housing_related(title) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_keywords.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'keywords'`

- [ ] **Step 3: Implement `keywords.py`**

```python
HOUSING_KEYWORDS = [
    "hébergement",
    "hebergement",
    "logement",
    "cité universitaire",
    "cite universitaire",
    "résidence",
    "residence",
    "internat",
    "chambre",
    "سكن",
    "مبيت",
    "الإقامة",
    "دار الطالب",
]


def is_housing_related(title: str) -> bool:
    lowered = title.lower()
    return any(keyword.lower() in lowered for keyword in HOUSING_KEYWORDS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_keywords.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add keywords.py tests/test_keywords.py
git commit -m "Add housing keyword matcher"
```

---

### Task 3: State persistence module

**Files:**
- Create: `state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing from other modules.
- Produces: `state.DEFAULT_STATE: dict` (`{"last_seen_id": 0, "last_heartbeat_utc": None, "failure_count": 0}`), `state.load_state(path: pathlib.Path) -> dict`, `state.save_state(path: pathlib.Path, state: dict) -> None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_state.py`:

```python
import json

from state import DEFAULT_STATE, load_state, save_state


def test_load_state_returns_defaults_when_file_missing(tmp_path):
    path = tmp_path / "state.json"

    state = load_state(path)

    assert state == DEFAULT_STATE


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "state.json"
    original = {"last_seen_id": 139, "last_heartbeat_utc": "2026-08-04T12:00:00+00:00", "failure_count": 0}

    save_state(path, original)
    loaded = load_state(path)

    assert loaded == original


def test_load_state_fills_missing_keys_with_defaults(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"last_seen_id": 5}), encoding="utf-8")

    state = load_state(path)

    assert state == {"last_seen_id": 5, "last_heartbeat_utc": None, "failure_count": 0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'state'`

- [ ] **Step 3: Implement `state.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add state.py tests/test_state.py
git commit -m "Add state.json load/save helpers"
```

---

### Task 4: Pushover client module

**Files:**
- Create: `pushover.py`
- Test: `tests/test_pushover.py`

**Interfaces:**
- Consumes: nothing from other modules.
- Produces: `pushover.PUSHOVER_API_URL: str`, `pushover.PushoverError(RuntimeError)`, `pushover.send_pushover(user_key: str, api_token: str, message: str, title: str | None = None, priority: int = 0, sound: str | None = None, retry: int | None = None, expire: int | None = None, timeout: int = 15) -> dict`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_pushover.py`:

```python
from unittest.mock import patch, MagicMock

import pytest

from pushover import send_pushover, PushoverError, PUSHOVER_API_URL


@patch("pushover.requests.post")
def test_send_pushover_posts_expected_normal_priority_payload(mock_post):
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"status": 1})

    send_pushover("user123", "token456", message="hello", title="Hi")

    mock_post.assert_called_once_with(
        PUSHOVER_API_URL,
        data={
            "token": "token456",
            "user": "user123",
            "message": "hello",
            "priority": 0,
            "title": "Hi",
        },
        timeout=15,
    )


@patch("pushover.requests.post")
def test_send_pushover_emergency_priority_includes_retry_and_expire(mock_post):
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"status": 1})

    send_pushover(
        "user123", "token456", message="urgent", title="Alert",
        priority=2, sound="siren", retry=60, expire=10800,
    )

    mock_post.assert_called_once_with(
        PUSHOVER_API_URL,
        data={
            "token": "token456",
            "user": "user123",
            "message": "urgent",
            "priority": 2,
            "title": "Alert",
            "sound": "siren",
            "retry": 60,
            "expire": 10800,
        },
        timeout=15,
    )


@patch("pushover.requests.post")
def test_send_pushover_raises_on_non_200(mock_post):
    mock_post.return_value = MagicMock(status_code=400, text="invalid token")

    with pytest.raises(PushoverError):
        send_pushover("user123", "token456", message="hello")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pushover.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pushover'`

- [ ] **Step 3: Implement `pushover.py`**

```python
import requests

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"


class PushoverError(RuntimeError):
    pass


def send_pushover(
    user_key: str,
    api_token: str,
    message: str,
    title: str | None = None,
    priority: int = 0,
    sound: str | None = None,
    retry: int | None = None,
    expire: int | None = None,
    timeout: int = 15,
) -> dict:
    payload = {
        "token": api_token,
        "user": user_key,
        "message": message,
        "priority": priority,
    }
    if title is not None:
        payload["title"] = title
    if sound is not None:
        payload["sound"] = sound
    if priority == 2:
        payload["retry"] = retry if retry is not None else 60
        payload["expire"] = expire if expire is not None else 10800

    response = requests.post(PUSHOVER_API_URL, data=payload, timeout=timeout)
    if response.status_code != 200:
        raise PushoverError(f"Pushover API returned {response.status_code}: {response.text}")

    return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pushover.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add pushover.py tests/test_pushover.py
git commit -m "Add Pushover client module"
```

---

### Task 5: Main orchestrator — `watch.py`

**Files:**
- Create: `watch.py`
- Test: `tests/test_watch.py`

**Interfaces:**
- Consumes: `scraper.SUPCOM_URL`, `scraper.Post`, `scraper.fetch_html`, `scraper.parse_latest_posts` (Task 1); `keywords.is_housing_related` (Task 2); `state.load_state`, `state.save_state` (Task 3); `pushover.send_pushover` (Task 4).
- Produces: `watch.STATE_PATH: Path`, `watch.HEARTBEAT_INTERVAL: datetime.timedelta` (1 hour), `watch.run_check(user_key: str, api_token: str, dry_run: bool = False) -> None`, `watch.send_test_notification(user_key: str, api_token: str, emergency: bool = False) -> None`, `watch.main() -> None` (CLI entry point, parses `--dry-run`, `--test-notify`, `--emergency`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_watch.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_watch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'watch'`

- [ ] **Step 3: Implement `watch.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_watch.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests across all modules PASS (19 passed)

- [ ] **Step 6: Commit**

```bash
git add watch.py tests/test_watch.py
git commit -m "Add watch.py orchestrator with heartbeat, dry-run, and test-notify"
```

---

### Task 6: GitHub Actions workflow, README, and repo setup

**Files:**
- Create: `.github/workflows/watch.yml`
- Create: `README.md`
- Create: `.gitignore`

**Interfaces:**
- Consumes: `watch.py` as the workflow's entry point (Task 5).
- Produces: nothing consumed by other tasks — this is the final integration task.

- [ ] **Step 1: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 2: Create the GitHub Actions workflow**

Create `.github/workflows/watch.yml`:

```yaml
name: SUP'COM dorm watcher

on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run watcher
        env:
          PUSHOVER_USER_KEY: ${{ secrets.PUSHOVER_USER_KEY }}
          PUSHOVER_API_TOKEN: ${{ secrets.PUSHOVER_API_TOKEN }}
        run: python watch.py

      - name: Commit updated state
        run: |
          git config user.name "supcom-dorm-watcher-bot"
          git config user.email "actions@users.noreply.github.com"
          git add state.json
          git diff --staged --quiet || git commit -m "Update watcher state [skip ci]"
          git push
```

- [ ] **Step 3: Write the README with full setup instructions**

Create `README.md`:

```markdown
# SUP'COM Dorm Watcher

Watches https://www.supcom.tn/ for new news posts and sends a Pushover alert the moment
one appears — a loud, repeating "emergency" alert if the post looks housing/dorm-related,
a quiet normal ping otherwise. Sends an hourly heartbeat so you know it's still running.

## One-time setup

1. **Create a Pushover account** at https://pushover.net and note your **User Key** (shown
   on your dashboard after login).
2. **Buy the Pushover app** on your phone (iOS/Android, one-time purchase, ~$5) and log in
   with the same account so it can receive pushes.
3. **Create a Pushover Application** at https://pushover.net/apps/build (any name, e.g.
   "SUP'COM Watcher") and note the **API Token/Key** it generates.
4. **Push this repo to GitHub** (create a new empty repo on GitHub first, then):
   ```bash
   git remote add origin <your-repo-url>
   git push -u origin main
   ```
5. **Add repo secrets**: on GitHub, go to Settings → Secrets and variables → Actions, and
   add two repository secrets:
   - `PUSHOVER_USER_KEY` — your User Key from step 1.
   - `PUSHOVER_API_TOKEN` — your API Token from step 3.
6. **Trigger the first run manually**: go to the Actions tab → "SUP'COM dorm watcher" →
   "Run workflow". This bootstraps `state.json` with the current latest post id and sends
   no alerts (there's nothing new yet). After this, it checks automatically every 5 minutes.

## Testing it actually works

Run locally (requires Python 3.12+ and the same two env vars set):

```bash
pip install -r requirements.txt
export PUSHOVER_USER_KEY=your_user_key
export PUSHOVER_API_TOKEN=your_api_token

python watch.py --test-notify              # sends one real normal test push
python watch.py --test-notify --emergency  # sends one real EMERGENCY test push — confirm
                                            # it actually rings loudly and repeats on your phone
python watch.py --dry-run                  # runs the real check against the live site but
                                            # only prints what it would send, sends nothing
```

## Running the tests

```bash
pip install -r requirements.txt
pytest -v
```
```

- [ ] **Step 4: Verify the full test suite still passes**

Run: `pytest -v`
Expected: all tests PASS (19 passed)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/watch.yml README.md .gitignore
git commit -m "Add GitHub Actions workflow and setup README"
```

- [ ] **Step 6: Manual verification (not automated — requires the user's own Pushover account)**

This step cannot be done by an automated worker since it needs the user's real Pushover
credentials and phone. Hand back to the user with these instructions:

1. Follow the README's "One-time setup" section (Pushover account, app purchase, API
   token, push to GitHub, add secrets).
2. Run `python watch.py --test-notify --emergency` locally to confirm the loud/repeating
   alert actually behaves as expected on their phone before relying on the live workflow.
3. Manually trigger the workflow once via "Run workflow" in the GitHub Actions tab to
   confirm the bootstrap run completes and `state.json` gets committed back to the repo.
```

