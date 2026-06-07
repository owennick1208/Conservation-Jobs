"""ReliefWeb international jobs  (api.reliefweb.int).

ReliefWeb is a UN (OCHA) service with a free, public JSON API. We pull jobs
tagged with the "Climate Change and Environment" theme, which covers
conservation / environment roles across Asia, Latin America, Africa, and the
Pacific. Each listing links back to its ReliefWeb posting (full description +
how to apply). No key needed — just a polite `appname`.

Docs: https://apidoc.reliefweb.int/
"""
import re

import requests

from .util import clean, to_iso

NAME = "ReliefWeb (international)"
KEY = "reliefweb"
API = "https://api.reliefweb.int/v2/jobs"
APPNAME = "conservation-jobs-aggregator"
THEME_ENV = 4588   # ReliefWeb theme id for "Climate Change and Environment"
LIMIT = 300        # API allows up to 1000 per call
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}


def _strip_html(s):
    return clean(re.sub(r"<[^>]+>", " ", s or ""))


def _parse(items):
    jobs = []
    for item in items:
        f = item.get("fields", {}) or {}
        title = clean(f.get("title"))
        if not title:
            continue

        sources = f.get("source") or []
        employer = clean(sources[0].get("name")) if sources else None

        countries = [clean(c.get("name")) for c in (f.get("country") or []) if c.get("name")]
        cities = [clean(c.get("name")) for c in (f.get("city") or []) if c.get("name")]
        loc_bits = ([cities[0]] if cities else []) + countries
        location = clean(", ".join(dict.fromkeys([b for b in loc_bits if b]))) or None

        cats = [clean(c.get("name")) for c in (f.get("career_categories") or []) if c.get("name")]
        desc = _strip_html(f.get("body"))
        if desc and len(desc) > 280:
            desc = desc[:277].rstrip() + "…"

        date = f.get("date") or {}
        url = f.get("url_alias") or f.get("url")
        jobs.append({
            "id": f"{KEY}-{item.get('id')}",
            "title": title,
            "description": desc,
            "url": url,
            "employer": employer,
            "employer_type": None,
            "location": location,
            "salary": None,
            "deadline": to_iso(date.get("closing")),
            "deadline_raw": clean(date.get("closing")),
            "published": to_iso(date.get("created")),
            "tags": cats[:4],
            "detail_url": url,
            "source": NAME,
            "source_key": KEY,
        })
    return jobs


def scrape():
    payload = {
        "limit": LIMIT,
        "preset": "latest",
        "filter": {"field": "theme.id", "value": [THEME_ENV]},
        "fields": {"include": [
            "title", "url", "url_alias", "date.closing", "date.created",
            "source.name", "country.name", "city.name", "career_categories.name", "body",
        ]},
    }
    # Primary: POST with browser-like headers (the default Python UA gets a 403).
    try:
        resp = requests.post(API, params={"appname": APPNAME}, json=payload,
                             headers=HEADERS, timeout=40)
        if resp.status_code == 200:
            return _parse(resp.json().get("data", []))
    except requests.RequestException:
        pass

    # Fallback: the same query as a GET request.
    params = {
        "appname": APPNAME, "limit": LIMIT, "preset": "latest",
        "filter[field]": "theme.id", "filter[value][]": THEME_ENV,
        "fields[include][]": [
            "title", "url", "url_alias", "date.closing", "date.created",
            "source.name", "country.name", "city.name", "career_categories.name", "body",
        ],
    }
    resp = requests.get(API, params=params, headers=HEADERS, timeout=40)
    resp.raise_for_status()
    return _parse(resp.json().get("data", []))
