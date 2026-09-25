#!/usr/bin/env python3
"""
DevOps, DevSecOps & Meetups daily digest.

Pulls:
  * DevOps & Cloud news      — RSS feeds            (sources.DEVOPS_FEEDS)
  * DevSecOps news           — RSS feeds + CISA KEV (sources.DEVSECOPS_FEEDS)
  * Meetups & events         — public iCal feeds    (sources.MEETUP_GROUPS / EXTRA_ICAL_FEEDS)
and renders docs/index.html (GitHub Pages) plus docs/data.json.

Usage:
    python fetch_devops_news.py            # build docs/
    python fetch_devops_news.py --check    # test every source, print status, build nothing

Run daily by .github/workflows/daily-digest.yml.

Etiquette: every request sends an identifying User-Agent, has a timeout, and
waits 1 s between requests to the same host. Only published feeds (RSS/iCal/
JSON) are read — no HTML scraping — so nothing here bypasses robots.txt.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests

import sources as S

USER_AGENT = "devops-digest/2.0 (+https://github.com/shailapps/devops-digest)"
TIMEOUT = 20
PER_HOST_DELAY = 1.0
LOOKBACK_HOURS = 48              # news window (wide enough that a delayed run misses nothing)
MAX_ITEMS_PER_FEED = 8
LOCAL_TZ = ZoneInfo(S.LOCAL_TIMEZONE)
DOCS = Path("docs")

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_last_hit: dict[str, float] = {}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def http_get(url: str) -> requests.Response:
    host = urlparse(url).netloc
    wait = PER_HOST_DELAY - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()
    resp = _session.get(url, timeout=TIMEOUT)
    if resp.status_code == 429:                       # one polite retry on rate limit
        time.sleep(min(int(resp.headers.get("Retry-After", "10") or 10), 60))
        resp = _session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


# --------------------------------------------------------------------------- #
# News (RSS / Atom)
# --------------------------------------------------------------------------- #
def parse_date(entry) -> datetime | None:
    for key in ("published", "updated"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def fetch_feeds(feeds: list[dict], keywords: list[str] | None = None) -> tuple[list[dict], list[str]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items, errors = [], []
    for feed in feeds:
        try:
            parsed = feedparser.parse(http_get(feed["url"]).content)
            if parsed.bozo and not parsed.entries:
                errors.append(f"{feed['name']}: could not parse feed")
                continue
            for entry in parsed.entries[:MAX_ITEMS_PER_FEED * (3 if feed.get("keyword_filter") else 1)]:
                published = parse_date(entry)
                if published and published < cutoff:
                    continue
                title = (entry.get("title") or "Untitled").strip()
                if feed.get("keyword_filter") and keywords:
                    text = f"{title} {entry.get('summary', '')}".lower()
                    if not any(k in text for k in keywords):
                        continue
                items.append({
                    "source": feed["name"], "category": feed["category"], "title": title,
                    "link": entry.get("link", "#"), "published": published,
                })
        except Exception as exc:  # one broken feed never fails the run
            errors.append(f"{feed['name']}: {exc}")
    return dedupe(items), errors


def dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for it in sorted(items, key=lambda i: i["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        key = re.sub(r"\W+", " ", it["title"].lower()).strip()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def fetch_cisa_kev() -> tuple[list[dict], list[str]]:
    try:
        data = http_get(S.CISA_KEV_URL).json()
    except Exception as exc:
        return [], [f"CISA KEV: {exc}"]
    cutoff = date.today() - timedelta(days=S.CISA_KEV_LOOKBACK_DAYS)
    out = []
    for v in data.get("vulnerabilities", []):
        try:
            added = date.fromisoformat(v["dateAdded"])
        except (KeyError, ValueError):
            continue
        if added < cutoff:
            continue
        ransomware = " · used in ransomware" if v.get("knownRansomwareCampaignUse") == "Known" else ""
        out.append({
            "source": "CISA KEV", "category": "Actively Exploited",
            "title": f"{v['cveID']} — {v.get('vendorProject', '')} {v.get('product', '')}: {v.get('vulnerabilityName', '')}{ransomware}",
            "link": f"https://nvd.nist.gov/vuln/detail/{v['cveID']}",
            "published": datetime(added.year, added.month, added.day, 12, tzinfo=timezone.utc),
            "date_only": True,
        })
    out.sort(key=lambda i: i["published"], reverse=True)
    return out, []


# --------------------------------------------------------------------------- #
# Meetups (iCalendar)
# --------------------------------------------------------------------------- #
def _unescape(v: str) -> str:
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _parse_ical_dt(params: str, value: str) -> datetime | None:
    value = value.strip()
    try:
        if "VALUE=DATE" in params.upper() or re.fullmatch(r"\d{8}", value):
            d = datetime.strptime(value[:8], "%Y%m%d")
            return d.replace(tzinfo=LOCAL_TZ)
        dt = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
        if value.endswith("Z"):
            return dt.replace(tzinfo=timezone.utc)
        m = re.search(r"TZID=([^;:]+)", params)
        try:
            tz = ZoneInfo(m.group(1).strip('"')) if m else LOCAL_TZ
        except Exception:
            tz = LOCAL_TZ
        return dt.replace(tzinfo=tz)
    except ValueError:
        return None


def parse_ical(text: str) -> list[dict]:
    """Minimal RFC 5545 VEVENT reader (enough for Meetup/Luma/Google calendars)."""
    lines: list[str] = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]                       # unfold continuation lines
        else:
            lines.append(raw)
    events, cur = [], None
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, value = line.split(":", 1)
            name, _, params = head.partition(";")
            name = name.upper()
            if name in ("DTSTART", "DTEND"):
                cur[name.lower()] = _parse_ical_dt(params, value)
            elif name in ("SUMMARY", "LOCATION", "URL", "DESCRIPTION", "STATUS"):
                cur[name.lower()] = _unescape(value).strip()
    return events


def classify_location(location: str, description: str, url: str) -> str | None:
    loc = f" {location.lower()} "
    if any(k in loc for k in S.LOCAL_AREA_KEYWORDS):
        return "NJ / NYC"
    blob = f"{loc} {description[:400].lower()}"
    if not location.strip() or any(k in blob for k in S.VIRTUAL_KEYWORDS):
        return "Virtual"
    return "Other" if S.INCLUDE_OTHER_LOCATIONS else None


def fetch_meetups() -> tuple[list[dict], list[str]]:
    calendars = [{"name": g, "url": f"https://www.meetup.com/{g}/events/ical/", "group_url": f"https://www.meetup.com/{g}/"}
                 for g in S.MEETUP_GROUPS] + list(S.EXTRA_ICAL_FEEDS)
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=S.MEETUP_HORIZON_DAYS)
    events, errors, seen = [], [], set()
    for cal in calendars:
        try:
            resp = http_get(cal["url"])
            if "BEGIN:VCALENDAR" not in resp.text[:500]:
                errors.append(f"{cal['name']}: not an iCal feed (check the group URL name)")
                continue
            for ev in parse_ical(resp.text):
                start = ev.get("dtstart")
                if not start or not (now - timedelta(hours=3) <= start <= horizon):
                    continue
                if ev.get("status", "").upper() == "CANCELLED":
                    continue
                where = classify_location(ev.get("location", ""), ev.get("description", ""), ev.get("url", ""))
                if where is None:
                    continue
                key = (ev.get("summary", "").lower(), start.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                events.append({
                    "group": cal["name"], "title": ev.get("summary", "Untitled event"),
                    "link": ev.get("url") or cal.get("group_url") or "#",
                    "start": start, "where": where, "location": ev.get("location", ""),
                })
        except Exception as exc:
            errors.append(f"{cal['name']}: {exc}")
    events.sort(key=lambda e: e["start"])
    return events, errors


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _fmt_news_time(dt: datetime | None, date_only: bool = False) -> str:
    if not dt:
        return "date unknown"
    return dt.strftime("added %b %d") if date_only else dt.astimezone(LOCAL_TZ).strftime("%b %d, %I:%M %p ET")


def render_news(items: list[dict], order: list[str], empty_msg: str) -> str:
    if not items:
        return f'<p class="empty">{empty_msg}</p>'
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it["category"], []).append(it)
    cats = [c for c in order if c in groups] + [c for c in groups if c not in order]
    out = ""
    for cat in cats:
        rows = "".join(f"""
          <li class="item">
            <a class="title" href="{html.escape(i['link'])}" target="_blank" rel="noopener">{html.escape(i['title'])}</a>
            <div class="meta"><span class="source">{html.escape(i['source'])}</span> &middot; {_fmt_news_time(i['published'], i.get('date_only', False))}</div>
          </li>""" for i in groups[cat])
        out += f'<section><h2>{html.escape(cat)}</h2><ul class="items">{rows}</ul></section>'
    return out


def render_meetups(events: list[dict]) -> str:
    if not events:
        how = ("No meetup calendars configured yet — add Meetup group names to "
               "<code>MEETUP_GROUPS</code> in <code>sources.py</code>." if not (S.MEETUP_GROUPS or S.EXTRA_ICAL_FEEDS)
               else f"No NJ / NYC or virtual events in the next {S.MEETUP_HORIZON_DAYS} days.")
        return f'<p class="empty">{how}</p>'
    rows = ""
    for e in events:
        local = e["start"].astimezone(LOCAL_TZ)
        badge = "local" if e["where"] == "NJ / NYC" else ("virtual" if e["where"] == "Virtual" else "other")
        loc = html.escape(e["location"][:120]) if e["location"] else ""
        rows += f"""
        <li class="item event" data-where="{badge}">
          <div class="date"><span class="mon">{local:%b}</span><span class="day">{local.day}</span><span class="dow">{local:%a}</span></div>
          <div class="body">
            <a class="title" href="{html.escape(e['link'])}" target="_blank" rel="noopener">{html.escape(e['title'])}</a>
            <div class="meta"><span class="badge {badge}">{html.escape(e['where'])}</span>
              {local:%I:%M %p} ET &middot; {html.escape(e['group'])}{(' &middot; ' + loc) if loc else ''}</div>
          </div>
        </li>"""
    return f"""
      <div class="filters">
        <label><input type="radio" name="where" value="all" checked> All</label>
        <label><input type="radio" name="where" value="local"> NJ / NYC</label>
        <label><input type="radio" name="where" value="virtual"> Virtual</label>
      </div>
      <ul class="items" id="events">{rows}</ul>"""


def render_html(news, devsec, meetups, errors) -> str:
    generated = datetime.now(LOCAL_TZ).strftime("%b %d, %Y %I:%M %p ET")
    errors_html = ""
    if errors:
        errors_html = (f'<details class="errors"><summary>{len(errors)} source(s) had issues</summary><ul>'
                       + "".join(f"<li>{html.escape(e)}</li>" for e in errors) + "</ul></details>")
    tabs = [
        ("news", f"DevOps &amp; Cloud <span>{len(news)}</span>",
         render_news(news, ["DevOps", "Cloud", "Cloud Native", "Community"], "No DevOps news in the last 48 hours.")),
        ("devsec", f"DevSecOps <span>{len(devsec)}</span>",
         render_news(devsec, ["Actively Exploited", "Advisories", "Supply Chain", "Cloud & Container", "AppSec", "Threats"],
                     "No DevSecOps items in the window.")),
        ("meetups", f"Meetups <span>{len(meetups)}</span>", render_meetups(meetups)),
    ]
    radios = "".join(f'<input type="radio" name="tab" id="t-{k}" {"checked" if i == 0 else ""}>' for i, (k, _, _) in enumerate(tabs))
    labels = "".join(f'<label for="t-{k}">{label}</label>' for k, label, _ in tabs)
    panels = "".join(f'<div class="panel" id="p-{k}">{body}</div>' for k, _, body in tabs)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DevOps Daily Digest</title>
<style>
  :root {{ --bg:#0d1117; --panel:#161b22; --border:#30363d; --text:#e6edf3; --muted:#8b949e; --accent:#58a6ff;
          --local:#3fb950; --virtual:#a371f7; --other:#8b949e; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:2rem 1rem 4rem; background:var(--bg); color:var(--text);
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:820px; margin:0 auto; }}
  header {{ margin-bottom:1.25rem; }}
  h1 {{ font-size:1.6rem; margin:0 0 .25rem; }}
  .subtitle {{ color:var(--muted); font-size:.9rem; }}
  input[name=tab] {{ display:none; }}
  .tabs {{ display:flex; gap:.4rem; flex-wrap:wrap; border-bottom:1px solid var(--border); margin-bottom:1.25rem; }}
  .tabs label {{ padding:.55rem .9rem; cursor:pointer; color:var(--muted); border-bottom:2px solid transparent; font-weight:500; }}
  .tabs label span {{ background:var(--panel); border:1px solid var(--border); border-radius:999px; padding:0 .45rem; font-size:.75rem; margin-left:.3rem; }}
  .panel {{ display:none; }}
  #t-news:checked ~ .tabs label[for=t-news], #t-devsec:checked ~ .tabs label[for=t-devsec],
  #t-meetups:checked ~ .tabs label[for=t-meetups] {{ color:var(--text); border-bottom-color:var(--accent); }}
  #t-news:checked ~ #p-news, #t-devsec:checked ~ #p-devsec, #t-meetups:checked ~ #p-meetups {{ display:block; }}
  section {{ margin-bottom:2rem; }}
  h2 {{ font-size:1rem; text-transform:uppercase; letter-spacing:.05em; color:var(--accent);
       border-bottom:1px solid var(--border); padding-bottom:.5rem; margin-bottom:.75rem; }}
  ul.items {{ list-style:none; margin:0; padding:0; }}
  li.item {{ background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:.85rem 1rem; margin-bottom:.6rem; }}
  a.title {{ color:var(--text); text-decoration:none; font-weight:500; line-height:1.4; overflow-wrap:anywhere; }}
  a.title:hover {{ color:var(--accent); }}
  .meta {{ color:var(--muted); font-size:.8rem; margin-top:.35rem; }}
  .event {{ display:flex; gap:1rem; align-items:flex-start; }}
  .date {{ min-width:3.2rem; text-align:center; border:1px solid var(--border); border-radius:8px; padding:.3rem 0; line-height:1.1; }}
  .date .mon, .date .dow {{ display:block; font-size:.7rem; color:var(--muted); text-transform:uppercase; }}
  .date .day {{ display:block; font-size:1.3rem; font-weight:600; }}
  .badge {{ font-size:.7rem; font-weight:600; border-radius:4px; padding:.05rem .4rem; color:#0d1117; margin-right:.25rem; }}
  .badge.local {{ background:var(--local); }} .badge.virtual {{ background:var(--virtual); }} .badge.other {{ background:var(--other); }}
  .filters {{ display:flex; gap:1rem; margin-bottom:.9rem; color:var(--muted); font-size:.9rem; }}
  .filters:has(input[value=local]:checked) ~ ul li[data-where]:not([data-where=local]),
  .filters:has(input[value=virtual]:checked) ~ ul li[data-where]:not([data-where=virtual]) {{ display:none; }}
  .errors {{ margin-top:2rem; color:var(--muted); font-size:.85rem; }}
  .empty {{ color:var(--muted); }}
  code {{ background:var(--panel); padding:0 .3rem; border-radius:4px; }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>DevOps Daily Digest</h1>
      <div class="subtitle">Updated {generated} &middot; DevOps &amp; Cloud, DevSecOps, and upcoming meetups</div>
    </header>
    {radios}
    <nav class="tabs">{labels}</nav>
    {panels}
    {errors_html}
  </div>
</body>
</html>"""


def _json_default(o):
    return o.isoformat() if isinstance(o, (datetime, date)) else str(o)


def main() -> int:
    check = "--check" in sys.argv
    news, e1 = fetch_feeds(S.DEVOPS_FEEDS)
    devsec, e2 = fetch_feeds(S.DEVSECOPS_FEEDS, S.DEVSECOPS_KEYWORDS)
    kev, e3 = fetch_cisa_kev()
    devsec = kev + devsec
    meetups, e4 = fetch_meetups()
    errors = e1 + e2 + e3 + e4

    if check:
        print(f"DevOps & Cloud: {len(news)} items | DevSecOps: {len(devsec)} (CISA KEV {len(kev)}) | Meetups: {len(meetups)}")
        for src in [f["name"] for f in S.DEVOPS_FEEDS + S.DEVSECOPS_FEEDS] + ["CISA KEV"] + S.MEETUP_GROUPS \
                   + [c["name"] for c in S.EXTRA_ICAL_FEEDS]:
            err = next((e for e in errors if e.startswith(src + ":")), None)
            print(f"  [{'ERR' if err else 'ok '}] {err or src}")
        return 0

    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(render_html(news, devsec, meetups, errors), encoding="utf-8")
    (DOCS / "data.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc), "devops": news, "devsecops": devsec,
         "meetups": meetups, "errors": errors}, default=_json_default, indent=2), encoding="utf-8")
    print(f"Wrote docs/index.html — {len(news)} DevOps, {len(devsec)} DevSecOps, "
          f"{len(meetups)} meetups ({len(errors)} source errors).")
    for e in errors:
        print("  !", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
