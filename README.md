# DevOps Daily Digest

A dashboard that updates itself every day. It has three tabs:

- **DevOps & Cloud:** news from AWS, Kubernetes, CNCF, HashiCorp, Docker, Azure, Google Cloud and r/devops.
- **DevSecOps:** CVEs that CISA has recently confirmed attackers are exploiting, Kubernetes security advisories, supply-chain news (GitHub Security, OpenSSF), container and cloud security news (Aqua, Sysdig), AppSec (Snyk), and The Hacker News filtered to DevSecOps topics.
- **Meetups:** upcoming NJ / NYC in-person and virtual events from the Meetup groups and calendars you choose.

A GitHub Actions workflow rebuilds it every morning, and GitHub Pages serves it at
`https://shailapps.github.io/devops-digest/`.

## How it works

1. `fetch_devops_news.py` reads the sources listed in `sources.py`. It writes the page to `docs/index.html` and the raw data to `docs/data.json`.
2. `.github/workflows/daily-digest.yml` runs the script daily at 11:00 UTC (7 AM EDT / 6 AM EST) and commits the updated `docs/` folder.
3. GitHub Pages serves `docs/` from the `main` branch.

It reads only published feeds: RSS, Atom, iCalendar and CISA's JSON file. It doesn't scrape HTML pages. Each request identifies itself with a User-Agent, has a timeout, and waits 1 second before hitting the same site again.

## Everyday use

| Task | How |
|---|---|
| Check that every source works | `python fetch_devops_news.py --check` |
| Build the page locally | `python fetch_devops_news.py`, then `open docs/index.html` |
| Run it now on GitHub | Actions tab → Daily DevOps & Cloud Digest → Run workflow |
| Change the schedule | Edit `cron` in the workflow file. The time is always UTC. |

## Adding meetups

Meetup doesn't offer a free search API, so you choose the groups to follow:

1. On meetup.com, set the location to Edison, NJ with a 50-mile radius. Search for DevOps, Kubernetes, Cloud Native, AWS, DevSecOps, OWASP or Platform Engineering. Also try "online" events for virtual ones.
2. Open a group. Copy the part of its URL that comes after `meetup.com/`, for example `meetup.com/some-devops-group/` → `some-devops-group`.
3. Add it to `MEETUP_GROUPS` in `sources.py`.

The script reads each group's public calendar at `meetup.com/<group>/events/ical/`. It labels each event **NJ / NYC** or **Virtual** based on its location and hides events elsewhere. To show those too, set `INCLUDE_OTHER_LOCATIONS = True`.

Any other public `.ics` calendar, such as a Luma calendar, can go in `EXTRA_ICAL_FEEDS`.

## Notes

- If a source fails, the page shows it under "source(s) had issues" and the run carries on. Run `--check` to see every source's status at once.
- Reddit sometimes blocks requests coming from GitHub Actions. If `r/devops` keeps failing, remove it or accept the gap.
- No API keys or secrets are needed.
