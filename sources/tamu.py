"""Texas A&M Natural Resources Job Board  (jobs.rwfm.tamu.edu).

The board paginates its search results with plain URL parameters
(?PageSize=&PageNum=) and renders every job's fields server-side, so we can
read the whole board without running any JavaScript:

  1. Walk pages /search/?PageSize=50&PageNum=1, 2, 3 ... until nothing new.
  2. For each job card, read the labelled fields straight off the results.

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
MAX_PAGES = 80      # safety cap (50 x 80 = 4,000 possible listings)
PAUSE = 0.5         # be polite between page requests

_TYPE = r"(Federal|State|County|City|Tribal Government|Private|Non[- ]?Profit|Academic)"
_LABELS = [
    "Application Deadline", "Published", "Starting Date", "Ending Date",
    "Hours per Week", "Salary", "Education Required", "Experience Required",
    "Location", "Locations",
]
_BOUNDARY = "|".join(re.escape(l) for l in _LABELS)


def _grab(text, label):
    """Pull a labelled value, stopping at the next known label."""
    m = re.search(
        rf"{re.escape(label)}\s*:\s*(.*?)(?=\s*(?:{_BOUNDARY})\s*:|$)", text
    )
    if not m:
        return None
    val = clean(m.group(1))
    if not val:
        return None
    # Trim trailing relative-time noise like "5 months ago" / "New".
    val = re.sub(r"\s*\b\d+\s+\w+\s+ago\b.*$", "", val)
    val = re.sub(r"\s*\bNew\b\s*$", "", val)
    return clean(val)


def _parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs, seen = [], set()

    for a in soup.select('a[href*="view-job"]'):
        m = re.search(r"id=(\d+)", a.get("href", ""))
        if not m:
            continue
        jid = m.group(1)
        if jid in seen:
            continue

        # Climb to the smallest enclosing block that holds this job's fields.
        container, node = None, a
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            if "Application Deadline" in node.get_text():
                container = node
                break
        if container is None:
            continue  # an anchor that isn't a real job card (e.g. a nav link)
        seen.add(jid)

        text = clean(container.get_text(" ")) or ""
        title = clean(a.get_text())
        if title:
            title = re.sub(r"^New\s+", "", title)

        employer = employer_type = None
        tail = text.split(title, 1)[1] if title and title in text else text
        em = re.match(rf"\s*(.+?)\s*\(\s*{_TYPE}\s*\)", tail)
        if em:
            employer, employer_type = clean(em.group(1)), em.group(2)

        deadline_raw = _grab(text, "Application Deadline")
        jobs.append({
            "id": f"{KEY}-{jid}",
            "_jid": jid,
            "title": title or "Untitled posting",
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
            break  # no new jobs on this page -> we've reached the end
        for j in new:
            seen.add(j.pop("_jid"))
            out.append(j)
        time.sleep(PAUSE)

    return out
