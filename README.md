# SUP'COM Dorm Watcher

Watches https://www.supcom.tn/ for new news posts and sends a Pushover alert the moment
one appears — a loud, repeating "emergency" alert if the post looks housing/dorm-related,
a quiet normal ping otherwise. Sends an hourly heartbeat so you know it's still running.

It also separately watches
[post #136](https://www.supcom.tn/details_actualite/136) (this year's registration
announcement) for its "الرابط" placeholder turning into a real link — confirmed against
last year's equivalent post, SUP'COM activates that existing placeholder rather than
publishing a whole new post when registration (including housing) opens. See
`link_watch.py`. **If SUP'COM's post id numbering changes next year, update
`WATCHED_POST_URL` in `link_watch.py` to point at the new year's announcement post.**

## One-time setup

1. **Create a Pushover account** at https://pushover.net and note your **User Key** (shown
   on your dashboard after login).
2. **Buy the Pushover app** on your phone (iOS/Android, one-time purchase, ~$5) and log in
   with the same account so it can receive pushes.
3. **Create a Pushover Application** at https://pushover.net/apps/build (any name, e.g.
   "SUP'COM Watcher") and note the **API Token/Key** it generates.
4. **Push this repo to GitHub** — create a new empty repo on GitHub first, and make it
   **public**, not private. This matters: `*/5 * * * *` is ~8,640 runs/month billed at a
   1-minute minimum each, and private repos get only 2,000 free Actions minutes/month
   (exhausted in about a week), while public repos get unlimited free minutes. Nothing here
   is sensitive — `state.json` is just the last-seen post id — and the two Pushover secrets
   stay encrypted repository secrets either way, never visible in the code.
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

## Keeping it alive (and what not to assume)

Two GitHub-side realities worth knowing, because neither is this code's fault and neither
announces itself:

- **GitHub disables scheduled workflows after 60 days of repository inactivity.** Worse, the
  automated `state.json` commits this workflow pushes with its own `GITHUB_TOKEN` may not
  count as activity for that clock — so the watcher can quietly switch itself off even
  though it's committing every 5 minutes. Glance at the Actions tab every few weeks, or push
  any manual commit, and re-enable the workflow there if GitHub has paused it. (If a
  heartbeat stops arriving on your phone, this is the first thing to check.)
- **`*/5 * * * *` is a best-effort request, not a guarantee.** GitHub's scheduled workflows
  queue behind overall platform load and routinely run late — sometimes by many minutes,
  occasionally skipping a slot entirely. So treat the real check interval as "usually around
  5 minutes, sometimes longer" and don't count on a hard 5-minute worst case for the
  first-come-first-served dorm race. For a genuinely time-critical window, also watch the
  site yourself; this bot is a safety net, not a stopwatch.

The hourly heartbeat exists precisely so silence is never ambiguous: if your phone hasn't
heard anything in well over an hour — healthy `✅ ... OK` *or* `⚠️ ... DEGRADED` — the
watcher itself has stopped, and that's the signal to go check the Actions tab.

## Running the tests

```bash
pip install -r requirements.txt
pytest -v
```

(The repo-root `conftest.py` is what makes the bare `pytest` command work — it puts the repo
root on `sys.path` so the test files can import `watch`, `scraper`, etc. On Windows, if
`python` opens the Microsoft Store, use `py -m pytest -v`.)
