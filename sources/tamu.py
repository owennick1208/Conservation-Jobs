"""Texas A&M Natural Resources Job Board  (jobs.rwfm.tamu.edu).

The big one — ~1,200 conservation / wildlife / fisheries postings. The search
results are loaded with JavaScript, so we:

  1. Pull job ids (view-job/?id=NNNN) from the search page(s).
  2. Fetch each posting's own detail page, which IS server-rendered, and read
     the labelled fields ("Posting:", "Application Deadline:", "Salary:", ...).

Reading by label keeps this resilient to markup changes.

NOTE ON PAGINATION: the public search uses an AJAX call we can't see from
outside, so by default this grabs the ids exposed on the first results page
(the most recently published jobs). If you want the full archive, open the
board in your browser, watch the Network tab while clicking "next page", and
paste the request URL into AJAX_URL below — the loop will then walk every page.
"""
import re
import time

import requests
from bs4 import BeautifulSoup

from .util import clean, to_iso

NAME = "TAMU Natural Resources Board"
KEY = "tamu"
SEARCH_URL = "https://jobs.rwfm.tamu.edu/search/"
DETAIL_URL = "https://jobs.rwfm.tamu.edu/view-job/?id={id}"
HEADERS = {"User-Agent": "Mozilla/5.0 (personal-wildlife-job-aggregator)"}

# Optional: paste the real paginated results endpoint here to fetch everything.
AJAX_URL = None
MAX_PAGES = 30          # safety cap when walking pages
REQUEST_PAUSE = 0.34    # be polite between detail-page fetches

_EMPLOYER_TYPE = r"(Federal|State|County|City|Tribal Government|Private)"


def _discover_ids(session):
    """Collect posting ids from the search page (and any reachable pages)."""
    ids, seen_pages = [], set()
    pages = [SEARCH_URL]
    if AJAX_URL:
        pages = [AJAX_URL.format(page=p) for p in range(1, MAX_PAGES + 1)]
    else:
        # Best-effort: many boards still honour a ?page= query on GET.
        pages += [f"{SEARCH_URL}?page={p}" for p in range(2, MAX_PAGES + 1)]

    for url in pages:
        if url in seen_pages:
            continue
        seen_pages.add(url)
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            break
        found = re.findall(r"view-job/\?id=(\d+)", resp.text)
        new = [i for i in found if i not in ids]
        if not new:
            # No new ids on this page -> assume we've reached the end.
            if url != SEARCH_URL:
                break
            continue
        ids.extend(new)
    return ids


def _field(text, label):
    m = re.search(rf"{label}\s*:?\s*(.+)", text)
    return clean(m.group(1)) if m else None


def _parse_detail(html, job_id):
    soup = BeautifulSoup(html, "html.parser")
    full = soup.get_text("\n")
    lines = [clean(x) for x in full.split("\n") if clean(x)]

    # Title: first meaningful heading that isn't the site name.
    title = None
    for tag in soup.find_all(["h1", "h2", "h3"]):
        t = clean(tag.get_text())
        if t and "job board" not in t.lower():
            title = t
            break

    # Employer + type, e.g. "Idaho Department of Fish and Game (State)".
    employer = employer_type = None
    for line in lines[:25]:
        m = re.match(rf"(.+?)\s*\(\s*{_EMPLOYER_TYPE}\s*\)\s*$", line)
        if m:
            employer, employer_type = clean(m.group(1)), m.group(2)
            break

    def field(label):
        for line in lines:
            if line.lower().startswith(label.lower()):
                return _field(line, label)
        return None

    # Application URL: the first external http link after the "Posting:" label.
    apply_url = None
    posting_anchor = soup.find(string=re.compile(r"Posting", re.I))
    if posting_anchor:
        nxt = posting_anchor.find_next("a", href=True)
        if nxt:
            apply_url = nxt["href"]
    if not apply_url:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "rwfm.tamu.edu" not in href:
                apply_url = href
                break

    deadline_raw = field("Application Deadline")
    detail = DETAIL_URL.format(id=job_id)
    return {
        "id": f"{KEY}-{job_id}",
        "title": title or "Untitled posting",
        "url": apply_url or detail,
        "employer": employer,
        "employer_type": employer_type,
        "location": field("Location") or field("Locations"),
        "salary": field("Salary"),
        "deadline": to_iso(deadline_raw),
        "deadline_raw": deadline_raw,
        "published": to_iso(field("Published")),
        "tags": [],
        "detail_url": detail,
        "source": NAME,
        "source_key": KEY,
    }


def scrape():
    session = requests.Session()
    session.headers.update(HEADERS)
    ids = _discover_ids(session)

    jobs = []
    for job_id in ids:
        try:
            resp = session.get(DETAIL_URL.format(id=job_id), timeout=30)
            resp.raise_for_status()
            jobs.append(_parse_detail(resp.text, job_id))
        except requests.RequestException:
            continue
        time.sleep(REQUEST_PAUSE)
    return jobs
