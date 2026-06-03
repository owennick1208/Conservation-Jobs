"""PARC herpetology job board  (parcplace.org).

A hand-curated WordPress page. The postings live in a plain <ul> under a
"Job Postings" heading; each <li> has a title link plus a few labelled lines
(Organization / Location / Salary / Deadline / Contact). We parse by those
labels so the scraper keeps working even if the page's styling changes.
"""
import re

import requests
from bs4 import BeautifulSoup

from .util import clean, make_id, to_iso

NAME = "PARC (herpetology)"
KEY = "parc"
URL = "https://parcplace.org/network/job-announcements/"
HEADERS = {"User-Agent": "Mozilla/5.0 (personal-wildlife-job-aggregator)"}
_LABELS = ("Organization", "Location", "Salary", "Deadline", "Contact")


def parse(html):
    soup = BeautifulSoup(html, "html.parser")

    heading = soup.find(
        lambda t: t.name in ("h1", "h2", "h3", "h4")
        and "job posting" in t.get_text(strip=True).lower()
    )
    if not heading:
        return []
    ul = heading.find_next("ul")
    if not ul:
        return []

    jobs = []
    for li in ul.find_all("li", recursive=False):
        title = url = None
        for a in li.find_all("a"):
            text = clean(a.get_text())
            if text:
                title, url = text, a.get("href")
                break
        if not title:
            continue

        # Parse the whole entry as one normalized string and pull each labelled
        # value, bounded by the next known label. This works whether the labels
        # sit in their own <b>/<strong> tags or are written inline.
        text = clean(li.get_text(" ")) or ""
        boundary = "|".join(_LABELS)

        def grab(label):
            m = re.search(
                rf"{label}\s*:\s*(.*?)(?=\s*(?:{boundary})\s*:|$)", text, re.I
            )
            return clean(m.group(1)) if m else None

        fields = {label.lower(): grab(label) for label in _LABELS}
        deadline_raw = fields.get("deadline")
        jobs.append({
            "id": make_id(KEY, url or title),
            "title": title,
            "url": url,
            "employer": fields.get("organization"),
            "employer_type": None,
            "location": fields.get("location"),
            "salary": fields.get("salary"),
            "deadline": to_iso(deadline_raw),
            "deadline_raw": deadline_raw,
            "published": None,
            "tags": [],
            "detail_url": None,
            "source": NAME,
            "source_key": KEY,
        })
    return jobs


def scrape():
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return parse(resp.text)
