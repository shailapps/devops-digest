"""
All sources for the digest live here. Edit this file to add/remove feeds or
Meetup groups — no other code changes needed.

Check every source before pushing:
    python fetch_devops_news.py --check
"""

# ---------------------------------------------------------------------------
# 1. DevOps & Cloud news  (RSS / Atom)
# ---------------------------------------------------------------------------
DEVOPS_FEEDS = [
    {"name": "AWS Blog",          "url": "https://aws.amazon.com/blogs/aws/feed/",            "category": "Cloud"},
    {"name": "AWS DevOps Blog",   "url": "https://aws.amazon.com/blogs/devops/feed/",          "category": "DevOps"},
    {"name": "Kubernetes Blog",   "url": "https://kubernetes.io/feed.xml",                     "category": "Cloud Native"},
    {"name": "CNCF Blog",         "url": "https://www.cncf.io/feed/",                           "category": "Cloud Native"},
    {"name": "HashiCorp Blog",    "url": "https://www.hashicorp.com/blog/feed.xml",             "category": "DevOps"},
    {"name": "Docker Blog",       "url": "https://www.docker.com/blog/feed/",                   "category": "Cloud Native"},
    # The old azurecomcdn.azureedge.net feed was retired; this is its replacement.
    {"name": "Azure Updates",     "url": "https://www.microsoft.com/releasecommunications/api/v2/azure/rss", "category": "Cloud"},
    {"name": "Google Cloud Blog", "url": "https://cloudblog.withgoogle.com/rss/",               "category": "Cloud"},
    {"name": "r/devops",          "url": "https://www.reddit.com/r/devops/.rss",                "category": "Community"},
]

# ---------------------------------------------------------------------------
# 2. DevSecOps news
#    keyword_filter=True -> general security outlets; keep only items that
#    match DEVSECOPS_KEYWORDS so the tab stays DevSecOps-focused.
# ---------------------------------------------------------------------------
DEVSECOPS_FEEDS = [
    {"name": "Kubernetes CVE Feed", "url": "https://kubernetes.io/docs/reference/issues-security/official-cve-feed/feed.xml",
     "category": "Advisories"},
    {"name": "GitHub Security Blog", "url": "https://github.blog/security/feed/",   "category": "Supply Chain"},
    {"name": "OpenSSF",              "url": "https://openssf.org/feed/",            "category": "Supply Chain"},
    {"name": "Aqua Security",        "url": "https://www.aquasec.com/feed/",        "category": "Cloud & Container"},
    {"name": "Sysdig",               "url": "https://sysdig.com/feed/",             "category": "Cloud & Container"},
    {"name": "Snyk",                 "url": "https://snyk.io/blog/feed/",           "category": "AppSec"},
    {"name": "The Hacker News",      "url": "https://feeds.feedburner.com/TheHackersNews",
     "category": "Threats", "keyword_filter": True},
]

DEVSECOPS_KEYWORDS = [
    "devsecops", "supply chain", "sbom", "slsa", "sigstore", "cosign", "container", "kubernetes", "k8s",
    "docker", "helm", "ci/cd", "pipeline", "github", "gitlab", "jenkins", "npm", "pypi", "maven",
    "open source", "dependency", "secrets", "iac", "terraform", "cloud", "aws", "azure", "gcp",
    "misconfiguration", "zero-day", "cve-", "ransomware", "api security", "identity", "iam",
]

# CISA Known Exploited Vulnerabilities — newly added CVEs are high-signal for patching.
CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CISA_KEV_LOOKBACK_DAYS = 7

# ---------------------------------------------------------------------------
# 3. Meetups & events  (public iCalendar feeds — no scraping, no API key)
# ---------------------------------------------------------------------------
# Meetup groups by their URL name: https://www.meetup.com/<URL-NAME>/
# How to add one: open the group on meetup.com, copy the part after
# "meetup.com/" (e.g. for https://www.meetup.com/some-devops-group/ use
# "some-devops-group"). The script reads the group's public calendar at
# https://www.meetup.com/<URL-NAME>/events/ical/
#
# Suggested searches on meetup.com (location: Edison, NJ, radius 50 mi):
#   DevOps · Kubernetes · Cloud Native · AWS · DevSecOps · OWASP · Platform Engineering
MEETUP_GROUPS = [
    # "your-devops-group-urlname",
    # "your-kubernetes-group-urlname",
]

# Any other public .ics calendar (Luma calendars, conference/community calendars…).
EXTRA_ICAL_FEEDS = [
    # {"name": "Some Community Calendar", "url": "https://example.com/events.ics"},
]

MEETUP_HORIZON_DAYS = 60          # show events in the next N days
LOCAL_TIMEZONE = "America/New_York"

# Location matching: an event is "NJ / NYC" if its location matches any of these,
# "Virtual" if it looks online. Everything else is dropped unless INCLUDE_OTHER_LOCATIONS.
LOCAL_AREA_KEYWORDS = [
    "new jersey", ", nj", " nj ", "nj 0", "edison", "iselin", "woodbridge", "metuchen", "piscataway",
    "new brunswick", "princeton", "jersey city", "hoboken", "newark", "parsippany", "morristown",
    "new york", ", ny", " ny ", "ny 1", "manhattan", "brooklyn", "queens", "nyc",
]
VIRTUAL_KEYWORDS = ["online", "virtual", "zoom", "google meet", "teams.microsoft", "webinar", "livestream", "youtube"]
INCLUDE_OTHER_LOCATIONS = False
