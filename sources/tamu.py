"""Texas A&M Natural Resources Job Board  (jobs.rwfm.tamu.edu).

The board paginates its search results with plain URL parameters
(?PageSize=&PageNum=) and renders every job's fields server-side, so we can
read the whole board without running any JavaScript:

  1. Walk pages /search/?PageSize=50&PageNum=1, 2, 3 ... until nothing new.
  2. For each job card, read the title, a short description, and the labelled
     fields straight off the results.

Each listing links to its posting page on the board, which carries the
employer's own application link.
"""
import re
import time

import requests
from bs4 import BeautifulSoup

from .util import clean, to_iso

NAME = "TAMU Natural Resources Board"
KEY = "tamu"
BASE = "https://jobs.rwfm.tamu.edu"
SEARCH = BASE + "/search/?PageSize={size}&PageNum={num}"
DETAIL = BASE + "/view-job/?id={id}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; conservation-jobs-aggregator/1.0)"}

PAGE_SIZE = 50
MAX_PAGES = 80      # safety cap
PAUSE = 0.5         # be polite between page requests

# Link text that is a button, not a job title.
_STOP_TITLES = {"view", "view job", "details", "view details", "apply",
                "apply now", "more", "read more", "view posting"}
_TYPE = r"(Federal|State|County|City|Tribal Government|Private|Non[- ]?Profit|Academic)"
_VALUE_LABELS = [
    "Application Deadline", "Published", "Starting Date", "Ending Date",
    "Hours per Week", "Salary", "Education Required", "Experience Required",
    "Location", "Locations",
]
# Boundary terms also include section headers that may lack a colon.
_BOUNDARY = "|".join(re.escape(l) for l in _VALUE_LABELS + ["Description", "Contact"])


def _grab(text, label):
    m = re.search(rf"{re.escape(label)}\s*:\s*(.*?)(?=\s*(?:{_BOUNDARY})\s*:?|$)", text)
    if not m:
        return None
    val = clean(m.group(1))
    if not val:
        return None
    val = re.sub(r"\s*\b\d+\s+\w+\s+ago\b.*$", "", val)   # "5 months ago"
    val = re.sub(r"\s*\bNew\b\s*$", "", val)
    val = re.sub(r"\s*\b(?:View|Apply|Details|More)\b\s*$", "", val, flags=re.I)
    return clean(val)


def _description(text):
    m = re.search(r"Description\s*:?\s*(.*?)(?=\s*Contact\b|$)", text)
    if not m:
        return None
    val = clean(m.group(1))
    if not val:
        return None
    return (val[:277] + "…") if len(val) > 280 else val


def _parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = {}  # jid -> {"container", "title"}

    for a in soup.select('a[href*="view-job"]'):
        m = re.search(r"id=(\d+)", a.get("href", ""))
        if not m:
            continue
        jid = m.group(1)
        txt = clean(a.get_text())

        entry = cards.get(jid)
        if entry is None:
            container, node = None, a
            for _ in range(6):
                node = node.parent
                if node is None:
                    break
                if "Application Deadline" in node.get_text():
                    container = node
                    break
            if container is None:
                continue  # a nav/footer link, not a job card
            entry = {"container": container, "title": None}
            cards[jid] = entry

        # Pick a real title: skip button text like "View"; prefer the longest.
        if txt and txt.lower() not in _STOP_TITLES:
            if not entry["title"] or len(txt) > len(entry["title"]):
                entry["title"] = txt

    jobs = []
    for jid, entry in cards.items():
        container = entry["container"]
        text = clean(container.get_text(" ")) or ""
        title = entry["title"]

        # Fallback 1: a heading element inside the card.
        if not title:
            h = container.find(["h1", "h2", "h3", "h4", "h5"])
            if h:
                title = clean(h.get_text())

        # Employer + type, e.g. "Idaho Department of Fish and Game (State)".
        employer = employer_type = None
        scan = text
        if title and title in text:
            scan = text.split(title, 1)[1]
        em = re.search(rf"(.+?)\s*\(\s*{_TYPE}\s*\)", scan)
        if em:
            employer, employer_type = clean(em.group(1)), em.group(2)

        # Fallback 2: derive a title from whatever sits before the employer.
        if not title and em:
            title = clean(scan[:em.start(1)]) or None
        title = re.sub(r"^New\s+", "", title) if title else "Untitled posting"

        deadline_raw = _grab(text, "Application Deadline")
        jobs.append({
            "id": f"{KEY}-{jid}",
            "_jid": jid,
            "title": title,
            "description": _description(text),
            "url": DETAIL.format(id=jid),
            "employer": employer,
            "employer_type": employer_type,
            "location": _grab(text, "Location") or _grab(text, "Locations"),
            "salary": _grab(text, "Salary"),
            "deadline": to_iso(deadline_raw),
            "deadline_raw": deadline_raw,
            "published": to_iso(_grab(text, "Published")),
            "tags": [],
            "detail_url": DETAIL.format(id=jid),
            "source": NAME,
            "source_key": KEY,
        })
    return jobs


def scrape():
    session = requests.Session()
    session.headers.update(HEADERS)

    out, seen = [], set()
    for num in range(1, MAX_PAGES + 1):
        try:
            resp = session.get(SEARCH.format(size=PAGE_SIZE, num=num), timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            break
        page = _parse_page(resp.text)
        new = [j for j in page if j["_jid"] not in seen]
        if not new:
            break
        for j in new:
            seen.add(j.pop("_jid"))
            out.append(j)
        time.sleep(PAUSE)
    return out
