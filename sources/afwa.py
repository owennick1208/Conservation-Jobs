"""Association of Fish & Wildlife Agencies — careers page (fishwildlife.org/careers).

A curated list of openings at AFWA member agencies (state + federal fish &
wildlife agencies) and some partner organizations. Each entry is a job title
that links to the employer's own posting, followed by the agency name. We read
that list and link straight out to each posting; we do NOT fetch the downstream
pages (many sit on systems that don't permit scraping).
"""
import re

import requests
from bs4 import BeautifulSoup

from .util import clean, make_id

NAME = "AFWA member agencies"
KEY = "afwa"
URL = "https://www.fishwildlife.org/careers"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_SKIP_LINKTEXT = {"contact", "careers", "search", "home"}


def _looks_real(html):
    return bool(html) and "Employment Opportunities" in html


def _fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.ok and _looks_real(r.text):
            return r.text
    except requests.RequestException:
        pass
    try:
        import cloudscraper
        r = cloudscraper.create_scraper().get(url, timeout=60)
        if r.ok and _looks_real(r.text):
            return r.text
    except Exception:
        pass
    try:
        meta = requests.get("https://archive.org/wayback/available",
                            params={"url": url}, timeout=30).json()
        snap = (meta.get("archived_snapshots") or {}).get("closest") or {}
        if snap.get("available") and snap.get("url"):
            raw = re.sub(r"/web/(\d+)/", r"/web/\1id_/", snap["url"])
            r = requests.get(raw, headers=HEADERS, timeout=60)
            if r.ok and _looks_real(r.text):
                return r.text
    except Exception:
        pass
    return ""


def _agency_after(a):
    """The agency name is the text right after the title link."""
    parts = []
    for sib in a.next_siblings:
        name = getattr(sib, "name", None)
        if name == "a":
            break
        if name in ("p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            break
        text = clean(sib.get_text()) if hasattr(sib, "get_text") else clean(str(sib))
        if text:
            parts.append(text)
    agency = clean(" ".join(parts))
    if not agency:
        parent = a.find_parent(["p", "li", "div"])
        if parent:
            ptext = clean(parent.get_text(" ")) or ""
            agency = clean(ptext.replace(clean(a.get_text()) or "", "", 1))
    return agency


def parse(html):
    soup = BeautifulSoup(html, "html.parser")

    start = soup.find(lambda t: t.name and "afwa members" in (clean(t.get_text()) or "").lower()
                      and len(clean(t.get_text()) or "") < 60)
    if not start:
        start = soup.find(lambda t: t.name in ("h1", "h2", "h3", "h4")
                          and (clean(t.get_text()) or "").lower() == "employment opportunities")
    if not start:
        return []
    end = soup.find(lambda t: t.name and "opportunities at afwa" in (clean(t.get_text()) or "").lower())

    jobs, seen = [], set()
    for el in start.find_all_next():
        if end is not None and el is end:
            break
        if getattr(el, "name", None) != "a" or not el.get("href"):
            continue
        href = el.get("href")
        if "fishwildlife.org" in href or href.startswith("#") or href.startswith("mailto:"):
            continue
        title = clean(el.get_text())
        if not title or title.lower() in _SKIP_LINKTEXT:
            continue
        if href in seen:
            continue
        seen.add(href)
        jobs.append({
            "id": make_id(KEY, href),
            "title": title,
            "description": None,
            "url": href,
            "employer": _agency_after(el),
            "employer_type": None,
            "location": None,
            "salary": None,
            "deadline": None,
            "deadline_raw": None,
            "published": None,
            "tags": [],
            "detail_url": None,
            "source": NAME,
            "source_key": KEY,
        })
    return jobs


def scrape():
    return parse(_fetch(URL))
