"""U.S. Fish & Wildlife Service postings, via the official USAJobs API.

Pulls ALL open FWS positions (biologists, refuge managers, technicians,
internships — everything), not just internships. Needs a free key:

  1. Get a key at https://developer.usajobs.gov/apirequest/
  2. Set repo secrets  USAJOBS_API_KEY  and  USAJOBS_EMAIL

If those aren't set, this source is skipped quietly.
"""
import os

import requests

from .util import clean, to_iso

NAME = "USAJobs · Fish & Wildlife Service"
KEY = "fws"
API = "https://data.usajobs.gov/api/search"
ORG_CODE = "IN15"               # USAJobs agency code for the Fish & Wildlife Service
ORG_MATCH = "fish and wildlife"  # safety filter on the hiring organization
MAX_PAGES = 6


def _query(headers, params):
    out = []
    for page in range(1, MAX_PAGES + 1):
        p = {**params, "ResultsPerPage": 500, "Page": page}
        r = requests.get(API, headers=headers, params=p, timeout=30)
        r.raise_for_status()
        items = r.json().get("SearchResult", {}).get("SearchResultItems", [])
        out.extend(items)
        if len(items) < 500:
            break
    return out


def scrape():
    api_key = os.environ.get("USAJOBS_API_KEY")
    email = os.environ.get("USAJOBS_EMAIL")
    if not api_key or not email:
        print("  [fws] skipped — USAJOBS_API_KEY / USAJOBS_EMAIL not set")
        return []

    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": api_key}

    # Primary: filter by the FWS agency code. Fallback: keyword, then org filter.
    items = _query(headers, {"Organization": ORG_CODE})
    if not items:
        items = _query(headers, {"Keyword": "U.S. Fish and Wildlife Service"})

    jobs, seen = [], set()
    for item in items:
        d = item.get("MatchedObjectDescriptor", {})
        org = clean(d.get("OrganizationName")) or ""
        if ORG_MATCH not in org.lower():
            continue
        pid = clean(d.get("PositionID")) or item.get("MatchedObjectId")
        if not pid or pid in seen:
            continue
        seen.add(pid)

        locs = d.get("PositionLocationDisplay") or ", ".join(
            clean(l.get("LocationName")) or "" for l in d.get("PositionLocation", []))
        salary = None
        rem = d.get("PositionRemuneration") or []
        if rem:
            lo, hi = clean(rem[0].get("MinimumRange")), clean(rem[0].get("MaximumRange"))
            unit = clean(rem[0].get("RateIntervalCode"))
            if lo and hi:
                salary = clean(f"${lo} – ${hi} {unit or ''}")
        details = (d.get("UserArea", {}) or {}).get("Details", {}) or {}
        desc = clean(details.get("JobSummary"))
        if desc and len(desc) > 280:
            desc = desc[:277].rstrip() + "…"
        apply_url = (d.get("ApplyURI") or [d.get("PositionURI")])[0]

        jobs.append({
            "id": f"{KEY}-{pid}",
            "title": clean(d.get("PositionTitle")) or "Untitled posting",
            "description": desc,
            "url": apply_url or d.get("PositionURI"),
            "employer": org,
            "employer_type": "Federal",
            "location": clean(locs),
            "salary": salary,
            "deadline": to_iso(d.get("ApplicationCloseDate")),
            "deadline_raw": clean(d.get("ApplicationCloseDate")),
            "published": to_iso(d.get("PublicationStartDate")),
            "tags": [],
            "detail_url": d.get("PositionURI"),
            "source": NAME,
            "source_key": KEY,
        })
    return jobs
