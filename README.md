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
