# DevOps & Cloud Daily Digest

A self-updating dashboard of the latest DevOps and cloud news, rebuilt every
day by GitHub Actions and published free via GitHub Pages.

## How it works

1. `fetch_devops_news.py` pulls RSS feeds from AWS, Kubernetes, CNCF,
   HashiCorp, Docker, Azure, Google Cloud, and r/devops, dedupes items,
   keeps only the last 48 hours, and writes `docs/index.html`.
2. `.github/workflows/daily-digest.yml` runs that script every day at
   12:00 UTC, then commits the updated `docs/index.html` back to the repo.
3. GitHub Pages serves the `docs/` folder as a live website.

## Setup (one-time, ~5 minutes)

1. **Create a new GitHub repo** (public or private — Pages works with both
   on a paid plan; public repos get Pages for free).
2. **Push these files** to the repo root, keeping the folder structure:
   ```
   your-repo/
     fetch_devops_news.py
     requirements.txt
     .github/workflows/daily-digest.yml
     docs/          (empty is fine, the workflow fills it in)
   ```
3. **Enable GitHub Pages:**
   - Go to your repo → Settings → Pages
   - Under "Build and deployment", set Source = "Deploy from a branch"
   - Branch = `main`, folder = `/docs`
   - Save
4. **Run it once manually** to generate the first version:
   - Go to the Actions tab → "Daily DevOps & Cloud Digest" → "Run workflow"
5. After it finishes, your dashboard is live at:
   `https://<your-username>.github.io/<your-repo>/`

From then on it updates itself daily — no server, no maintenance.

## Customizing

- **Change the schedule:** edit the `cron` line in
  `.github/workflows/daily-digest.yml`. `"0 12 * * *"` = 12:00 UTC daily.
  Cron times are always UTC in GitHub Actions — offset for Eastern time
  (e.g. `"0 12 * * *"` = 8:00 AM EDT / 7:00 AM EST).
- **Add or remove sources:** edit the `FEEDS` list at the top of
  `fetch_devops_news.py`. Any RSS/Atom feed URL works.
- **Change the lookback window:** `LOOKBACK_HOURS` in the same file
  (default 48, so nothing is missed if a run is delayed).
- **Add AI-written summaries instead of just headlines:** call the
  Anthropic API from `render_html()` per item, storing the key as a
  GitHub Actions secret (`ANTHROPIC_API_KEY`) rather than in code. Happy
  to build that version out if you want it.

## Notes

- If a feed is temporarily down, the script skips it and lists it under
  "feed(s) had issues" at the bottom of the page rather than failing the
  whole run.
- No secrets or API keys are required for this base version — it's pure
  RSS aggregation, so it costs nothing to run.
