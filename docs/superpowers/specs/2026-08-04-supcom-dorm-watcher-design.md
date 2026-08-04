# SUP'COM Dorm Announcement Watcher — Design

## Goal

SUP'COM (https://www.supcom.tn) posts dorm/housing application openings as a news item on
its site with no advance notice, and admission is first-come-first-served. This tool watches
the site's news feed and pushes a loud, hard-to-miss phone alert the moment a housing-related
post appears, so the user can apply within minutes of it going live.

## Architecture

- **Runtime**: a GitHub Actions scheduled workflow (`cron`, every 5 minutes) in its own new
  repo (`supcom-dorm-watcher`), separate from unrelated projects. GitHub Actions requires a
  real repo to run in.
- **Language**: Python (`requests` + `BeautifulSoup`). The site is server-rendered plain HTML
  (Laravel backend — confirmed via network inspection: no JSON API, content present in the
  initial HTML response), so no headless browser is required.
- **State**: a `state.json` file in the repo, committed back by the workflow after each run
  (GitHub Actions has no persistent disk between runs, so the repo itself is the store).
- **Notifications**: [Pushover](https://pushover.net). Normal priority for routine pings,
  priority 2 ("emergency" — repeats ~every 60s for up to 3h until manually acknowledged,
  overrides silent/DND) for housing-keyword matches. Requires the user's own Pushover
  account + app purchase, User Key, and Application API Token — both keys stored only as
  GitHub Actions encrypted secrets, never committed.

## Data flow (main loop, runs every 5 min)

1. GET `https://www.supcom.tn/`. Its "Dernières Actualités" section already lists
   title/date/link for the ~8 latest posts — no need to hit the separate `/actualites` page.
2. Parse each entry's numeric id out of its `/details_actualite/{id}` link (confirmed clean,
   sequential; current max observed is 139).
3. Compare every id found against `state.json`'s `last_seen_id`. Anything higher is new.
4. For each new post, oldest to newest:
   - Always send a normal-priority Pushover ping (title + direct link).
   - If the title matches a housing-keyword list (French: `hébergement`, `logement`,
     `cité universitaire`, `résidence`, `internat`, `chambre` — Arabic: `سكن`, `مبيت`,
     `الإقامة`, `دار الطالب`) → also send the emergency-priority alarm.
5. Update `state.json`'s `last_seen_id` to the new max, commit + push.
6. **First run bootstraps silently**: seeds `state.json` with whatever the current max id is
   without alerting on pre-existing posts.

## Heartbeat ("still alive") notification

Independent of whether anything new was found, the workflow sends one normal-priority
Pushover ping per hour confirming the bot is running and no new posts have appeared since
last check (or summarizing what it did find, if anything).

- `state.json` also tracks `last_heartbeat_utc`.
- Every run (every 5 min) checks: has ≥60 minutes passed since `last_heartbeat_utc`? If yes,
  send the heartbeat ping and update the timestamp. This piggybacks on the existing 5-minute
  cron rather than needing a second schedule.
- Message text: `"✅ SUP'COM watcher OK — last checked <time>, latest post is #<id>, no
  housing news yet."` (or, if new posts were found that hour, a short summary instead of the
  generic "no news" line).

## Fake/test notification mode

A CLI flag on the same script, for verifying the Pushover setup end-to-end without waiting
for a real post or a real hour to pass:

- `python watch.py --test-notify` → sends one real normal-priority Pushover push with clearly
  fake/labeled content (`"[TEST] This is a fake notification from the SUP'COM watcher."`), to
  confirm the User Key/API Token and phone delivery work.
- `python watch.py --test-notify --emergency` → sends one real priority-2 emergency push
  (`"[TEST] This is a fake EMERGENCY alert..."`) so the user can confirm the loud/repeating/
  DND-override behavior actually fires on their phone before relying on it for the real thing.
- Separately, `python watch.py --dry-run` runs the real scrape/parse/keyword logic against the
  live site but only *prints* what it would have sent, sending nothing — for checking id
  parsing and keyword matching without spamming Pushover.

## State file schema

```json
{
  "last_seen_id": 139,
  "last_heartbeat_utc": "2026-08-04T12:00:00Z"
}
```

## Secrets / config

Stored as GitHub Actions encrypted repo secrets, read via environment variables:
- `PUSHOVER_USER_KEY`
- `PUSHOVER_API_TOKEN`

## Error handling

- If the fetch or parse fails (site down, layout changed), the run logs and exits — it does
  **not** crash the cron schedule, and does **not** advance `state.json` (so it re-checks
  next run).
- If it fails 3 runs in a row (~15 min), it sends one low-priority Pushover heads-up that the
  monitor itself is failing, so a broken watcher doesn't silently look like "all quiet."

## Testing

- `--dry-run` (see above) against the live site, no alerts sent.
- `--test-notify` / `--test-notify --emergency` (see above) for real end-to-end Pushover
  delivery checks.
- One unit test using a saved HTML fixture with a fake "new" post id to confirm id-diffing and
  keyword-matching logic, without hitting the network.

## Out of scope / simplifications

- No web UI or dashboard — this is a headless script + phone push only.
- No attempt to detect changes to *existing* posts (edits), only new post ids appearing.
- Keyword list is a plain hardcoded list in the script, not a config file — easy to edit
  directly if wording needs tuning later.
