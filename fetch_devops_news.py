#!/usr/bin/env python3
"""
Fetches the latest DevOps & Cloud news from a curated set of RSS feeds,
dedupes and sorts them, and renders a static HTML dashboard.

Run daily by .github/workflows/daily-digest.yml
Output: docs/index.html  (served by GitHub Pages)
"""

import feedparser
import html
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

# ---- Sources -----------------------------------------------------------
# Add/remove feeds here. "category" is just for grouping/display.
FEEDS = [
    {"name": "AWS Blog",          "url": "https://aws.amazon.com/blogs/aws/feed/",              "category": "Cloud"},
    {"name": "AWS DevOps Blog",   "url": "https://aws.amazon.com/blogs/devops/feed/",            "category": "DevOps"},
    {"name": "Kubernetes Blog",   "url": "https://kubernetes.io/feed.xml",                       "category": "Cloud Native"},
    {"name": "CNCF Blog",         "url": "https://www.cncf.io/feed/",                             "category": "Cloud Native"},
    {"name": "HashiCorp Blog",    "url": "https://www.hashicorp.com/blog/feed.xml",               "category": "DevOps"},
    {"name": "Docker Blog",       "url": "https://www.docker.com/blog/feed/",                     "category": "Cloud Native"},
    {"name": "Azure Updates",     "url": "https://azurecomcdn.azureedge.net/en-us/updates/feed/", "category": "Cloud"},
    {"name": "Google Cloud Blog", "url": "https://cloudblog.withgoogle.com/rss/",                  "category": "Cloud"},
    {"name": "r/devops",          "url": "https://www.reddit.com/r/devops/.rss",                  "category": "Community"},
]

# Only keep items published within this window (hours). Widen if feeds are quiet.
LOOKBACK_HOURS = 48
MAX_ITEMS_PER_FEED = 8


def parse_date(entry):
    """Best-effort parse of an entry's published date to an aware datetime."""
    for key in ("published", "updated"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                pass
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def fetch_all():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items = []
    errors = []

    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            if parsed.bozo and not parsed.entries:
                errors.append(f"{feed['name']}: could not parse feed")
                continue

            for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:
                published = parse_date(entry)
                if published and published < cutoff:
                    continue

                items.append({
                    "source": feed["name"],
                    "category": feed["category"],
                    "title": entry.get("title", "Untitled").strip(),
                    "link": entry.get("link", "#"),
                    "published": published,
                })
        except Exception as exc:  # keep going even if one feed is down
            errors.append(f"{feed['name']}: {exc}")

    # Dedupe by normalized title (same story often appears on multiple feeds)
    seen = set()
    deduped = []
    for item in sorted(items, key=lambda i: i["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        key = item["title"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped, errors


def group_by_category(items):
    groups = {}
    for item in items:
        groups.setdefault(item["category"], []).append(item)
    # Stable, readable category order
    order = ["DevOps", "Cloud", "Cloud Native", "Community"]
    return {cat: groups[cat] for cat in order if cat in groups}


def render_html(items, errors):
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    groups = group_by_category(items)

    sections_html = ""
    for category, cat_items in groups.items():
        rows = ""
        for item in cat_items:
            when = item["published"].strftime("%b %d, %H:%M UTC") if item["published"] else "date unknown"
            rows += f"""
            <li class="item">
              <a class="title" href="{html.escape(item['link'])}" target="_blank" rel="noopener">{html.escape(item['title'])}</a>
              <div class="meta"><span class="source">{html.escape(item['source'])}</span> &middot; <span class="time">{when}</span></div>
            </li>"""
        sections_html += f"""
        <section>
          <h2>{html.escape(category)}</h2>
          <ul class="items">{rows}
          </ul>
        </section>"""

    errors_html = ""
    if errors:
        error_items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        errors_html = f"""
        <details class="errors">
          <summary>{len(errors)} feed(s) had issues</summary>
          <ul>{error_items}</ul>
        </details>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DevOps &amp; Cloud Daily Digest</title>
<style>
  :root {{
    --bg: #0d1117;
    --panel: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 2rem 1rem 4rem;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 780px; margin: 0 auto; }}
  header {{ margin-bottom: 2rem; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 0.25rem; }}
  .subtitle {{ color: var(--muted); font-size: 0.9rem; }}
  section {{ margin-bottom: 2rem; }}
  h2 {{
    font-size: 1rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--accent);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin-bottom: 0.75rem;
  }}
  ul.items {{ list-style: none; margin: 0; padding: 0; }}
  li.item {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.6rem;
  }}
  a.title {{
    color: var(--text);
    text-decoration: none;
    font-weight: 500;
    line-height: 1.4;
  }}
  a.title:hover {{ color: var(--accent); }}
  .meta {{ color: var(--muted); font-size: 0.8rem; margin-top: 0.35rem; }}
  .errors {{ margin-top: 2rem; color: var(--muted); font-size: 0.85rem; }}
  .empty {{ color: var(--muted); }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>DevOps &amp; Cloud Daily Digest</h1>
      <div class="subtitle">Last updated {generated_at} &middot; last {LOOKBACK_HOURS}h from {len(FEEDS)} sources</div>
    </header>
    {sections_html if items else '<p class="empty">No items found in the lookback window. Try again after the next run.</p>'}
    {errors_html}
  </div>
</body>
</html>"""


def main():
    items, errors = fetch_all()
    output = render_html(items, errors)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(output)
    print(f"Wrote docs/index.html with {len(items)} items ({len(errors)} feed errors).")


if __name__ == "__main__":
    main()
