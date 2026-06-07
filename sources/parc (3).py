"""PARC herpetology job board  (parcplace.org).

A hand-curated WordPress list. Postings sit between a "Job Postings" heading
and a "Career Development" heading; each item has a title (usually a link out
to the employer) followed by labelled lines: Organization / Location / Salary /
Deadline / Contact. We locate the section, collect the list items in it, and
read each by label, so the scraper tolerates markup changes.
"""
import re

import requests
from bs4 import BeautifulSoup

from .util import clean, make_id, to_iso

NAME = "PARC (herpetology)"
KEY = "parc"
URL = "https://parcplace.org/network/job-announcements/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
_LABELS = ("Organization", "Location", "Salary", "Deadline", "Contact")
_BOUNDARY = "|".join(_LABELS)


def _find_heading(soup, *needles):
    # exact match first, then a contains-match, over any element.
    for el in soup.find_all(True):
        t = clean(el.get_text())
        if t and t.lower() in needles:
            return el
    for el in soup.find_all(True):
        t = clean(el.get_text())
        if t and any(n in t.lower() for n in needles) and len(t) < 40:
            return el
    return None


def _grab(text, label):
    m = re.search(rf"{label}\s*:\s*(.*?)(?=\s*(?:{_BOUNDARY})\s*:|$)", text, re.I)
    return clean(m.group(1)) if m else None


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    start = _find_heading(soup, "job postings", "job announcements")
    if not start:
        return []
    end = _find_heading(soup, "career development", "career resources")

    items = []
    for el in start.find_all_next():
        if end is not None and el is end:
            break
        if getattr(el, "name", None) == "li":
            t = el.get_text(" ")
            if re.search(rf"(?:{_BOUNDARY})\s*:", t, re.I):
                items.append(el)

    jobs = []
    for li in items:
        url = None
        for a in li.find_all("a"):
            if clean(a.get_text()):
                url = a.get("href")
                break
        text = clean(li.get_text(" ")) or ""

        # Title: the first link's text, else the text before the first label.
        title = None
        for a in li.find_all("a"):
            if clean(a.get_text()):
                title = clean(a.get_text())
                break
        if not title:
            m = re.match(rf"\s*(.+?)\s*(?:{_BOUNDARY})\s*:", text, re.I)
            cand = clean(m.group(1)) if m else None
            if cand and not re.match(rf"(?:{_BOUNDARY})\s*:", cand, re.I):
                title = cand
        if not title:
            title = _grab(text, "Organization")  # no title given -> use employer
        if not title:
            continue

        deadline_raw = _grab(text, "Deadline")
        jobs.append({
            "id": make_id(KEY, url or title),
            "title": title,
            "description": None,
            "url": url,
            "employer": _grab(text, "Organization"),
            "employer_type": None,
            "location": _grab(text, "Location"),
            "salary": _grab(text, "Salary"),
            "deadline": to_iso(deadline_raw),
            "deadline_raw": deadline_raw,
            "published": None,
            "tags": [],
            "detail_url": None,
            "source": NAME,
            "source_key": KEY,
        })
    return jobs


def _looks_real(html):
    return bool(html) and "Job Postings" in html


def _fetch(url):
    """PARC sits behind Cloudflare, which serves data-center IPs a challenge
    page instead of the real one. Try three ways and keep the first that
    actually returns the postings."""
    # 1) Plain browser-like request (works from normal IPs).
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        try:
            s.get("https://parcplace.org/", timeout=30)
        except requests.RequestException:
            pass
        r = s.get(url, timeout=30)
        if r.ok and _looks_real(r.text):
            return r.text
    except requests.RequestException:
        pass

    # 2) Cloudflare-aware fetch (solves the basic JS challenge), if available.
    try:
        import cloudscraper
        r = cloudscraper.create_scraper().get(url, timeout=60)
        if r.ok and _looks_real(r.text):
            return r.text
    except Exception:
        pass

    # 3) Reader service fetches the rendered page for us and returns its HTML.
    try:
        r = requests.get(
            "https://r.jina.ai/" + url,
            headers={"X-Return-Format": "html", "User-Agent": HEADERS["User-Agent"]},
            timeout=60,
        )
        if r.ok and _looks_real(r.text):
            return r.text
    except requests.RequestException:
        pass

    # 4) Internet Archive snapshot. archive.org isn't Cloudflare-blocked, so this
    #    reliably returns the page's real content (possibly a little out of date).
    try:
        meta = requests.get("https://archive.org/wayback/available",
                            params={"url": url}, timeout=30).json()
        snap = (meta.get("archived_snapshots") or {}).get("closest") or {}
        if snap.get("available") and snap.get("url"):
            raw = re.sub(r"/web/(\d+)/", r"/web/\1id_/", snap["url"])  # raw archived HTML
            r = requests.get(raw, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=60)
            if r.ok and _looks_real(r.text):
                return r.text
    except Exception:
        pass

    return ""


def scrape():
    return parse(_fetch(URL))
