"""Texas A&M Natural Resources Job Board  (jobs.rwfm.tamu.edu).

The search page paginates with ?PageSize=&PageNum= and renders everything
server-side. Each page contains, for every job:
  * a results card  -> title (in a heading), employer + type, the labelled
    fields, any job-type tags, and a "View" link carrying the job id;
  * a detail block  -> the employer's application URL ("Posting:") and the
    full job description.
We read the cards for the structured fields and the detail blocks for the
description and direct apply link, matching the two up by title.
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
MAX_PAGES = 80
PAUSE = 0.5

_TYPE = r"(Federal|State|County|City|Tribal Government|Private|Non[- ]?Profit|Academic)"
_HEAD_SKIP = {"details", "description", "contact", "view", "results"}
_KNOWN_TAGS = [
    "Full-Time", "Part-Time / Temporary", "Volunteer / Training",
    "Undergraduate Opportunities", "Graduate Opportunities",
    "Faculty / Post-Doc Appointments", "Grant",
]
_VALUE_LABELS = ["Application Deadline", "Published", "Starting Date", "Ending Date",
                 "Hours per Week", "Salary", "Education Required", "Experience Required",
                 "Location", "Locations", "Tags"]
_BOUNDARY = "|".join(re.escape(l) for l in _VALUE_LABELS + ["Description", "Contact"])


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").lower()).strip()


def _grab(text, label):
    m = re.search(rf"{re.escape(label)}\s*:\s*(.*?)(?=\s*(?:{_BOUNDARY})\s*:?|$)", text)
    if not m:
        return None
    val = clean(m.group(1))
    if not val:
        return None
    val = re.sub(r"\s*\b\d+\s+\w+\s+ago\b.*$", "", val)
    val = re.sub(r"\s*\bNew\b\s*$", "", val)
    val = re.sub(r"\s*\b(?:View|Apply|Details|More)\b\s*$", "", val, flags=re.I)
    return clean(val)


def _detail_data(soup):
    """Map normalized title -> {'apply': url, 'desc': text} from detail blocks."""
    out = {}
    for h in soup.find_all("h3"):
        title = clean(h.get_text())
        if not title or _norm(title).startswith("results"):
            continue
        apply_url, desc_parts = None, []
        posting_seen = collecting = False
        node, steps = h, 0
        while steps < 500:
            steps += 1
            node = node.find_next()
            if node is None or getattr(node, "name", None) == "h3":
                break
            name = node.name or ""
            txt = clean(node.get_text()) if hasattr(node, "get_text") else None
            low = (txt or "").lower()
            if name in ("h4", "h5", "h6", "strong", "b", "dt", "p", "div"):
                if low.startswith("posting"):
                    posting_seen = True
                if low == "description":
                    collecting = True
                    continue
                if low == "contact":
                    collecting = False
            if name == "a" and posting_seen and not apply_url:
                href = node.get("href", "")
                if href.startswith("http") and "tamu.edu" not in href:
                    apply_url = href
            if collecting and name in ("p", "ul", "ol", "li", "div") and txt:
                desc_parts.append(txt)
        desc = clean(" ".join(desc_parts))
        if desc and len(desc) > 280:
            desc = desc[:277].rstrip() + "…"
        out[_norm(title)] = {"apply": apply_url, "desc": desc or None}
    return out


def _parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    details = _detail_data(soup)

    containers = {}
    for a in soup.select('a[href*="view-job"]'):
        m = re.search(r"id=(\d+)", a.get("href", ""))
        if not m:
            continue
        jid = m.group(1)
        if jid in containers:
            continue
        node = a
        for _ in range(7):
            node = node.parent
            if node is None:
                break
            if "Application Deadline" in node.get_text():
                containers[jid] = node
                break

    jobs = []
    for jid, container in containers.items():
        title = None
        for h in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            t = clean(h.get_text())
            if t and _norm(t) not in _HEAD_SKIP:
                title = t
                break
        text = clean(container.get_text(" ")) or ""

        employer = employer_type = None
        scan = text.split(title, 1)[1] if (title and title in text) else text
        em = re.search(rf"(.+?)\s*\(\s*{_TYPE}\s*\)", scan)
        if em:
            employer, employer_type = clean(em.group(1)), em.group(2)
        if not title:
            title = "Untitled posting"
        title = re.sub(r"^New\s+", "", title)

        tags = [t for t in _KNOWN_TAGS if t in text]
        det = details.get(_norm(title)) or {}
        deadline_raw = _grab(text, "Application Deadline")
        jobs.append({
            "id": f"{KEY}-{jid}",
            "_jid": jid,
            "title": title,
            "description": det.get("desc"),
            "url": det.get("apply") or DETAIL.format(id=jid),
            "employer": employer,
            "employer_type": employer_type,
            "location": _grab(text, "Location") or _grab(text, "Locations"),
            "salary": _grab(text, "Salary"),
            "deadline": to_iso(deadline_raw),
            "deadline_raw": deadline_raw,
            "published": to_iso(_grab(text, "Published")),
            "tags": tags,
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
