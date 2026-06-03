"""U.S. Fish & Wildlife Service postings, via the official USAJobs API.

The fws.gov/internships page has no listings of its own — it points to
USAJobs.gov. USAJobs has a clean, free API, but it needs a key:

  1. Get a free key at https://developer.usajobs.gov/apirequest/
  2. Set two environment variables (or GitHub repo secrets):
        USAJOBS_API_KEY = your key
        USAJOBS_EMAIL   = the email you registered with

If those aren't set, this source is skipped quietly.
"""
import os

import requests

from .util import clean, to_iso

NAME = "USAJobs · Fish & Wildlife Service"
KEY = "fws"
API = "https://data.usajobs.gov/api/search"
# Keep only results whose hiring org clearly belongs to FWS.
ORG_MATCH = "fish and wildlife"
# Tweak this to widen/narrow what counts as relevant.
KEYWORD = "internship fellowship"


def scrape():
    api_key = os.environ.get("USAJOBS_API_KEY")
    email = os.environ.get("USAJOBS_EMAIL")
    if not api_key or not email:
        print("  [fws] skipped — USAJOBS_API_KEY / USAJOBS_EMAIL not set")
        return []

    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": email,
        "Authorization-Key": api_key,
    }
    params = {"Keyword": KEYWORD, "ResultsPerPage": 500}
    resp = requests.get(API, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    items = (
        resp.json()
        .get("SearchResult", {})
        .get("SearchResultItems", [])
    )

    jobs = []
    for item in items:
        d = item.get("MatchedObjectDescriptor", {})
        org = clean(d.get("OrganizationName")) or ""
        if ORG_MATCH not in org.lower():
            continue

        locations = d.get("PositionLocationDisplay") or ", ".join(
            clean(loc.get("LocationName")) or "" for loc in d.get("PositionLocation", [])
        )
        salary = None
        rem = d.get("PositionRemuneration") or []
        if rem:
            r = rem[0]
            lo, hi, unit = r.get("MinimumRange"), r.get("MaximumRange"), clean(r.get("RateIntervalCode"))
            if lo and hi:
                salary = f"${lo} – ${hi} {unit or ''}".strip()

        jobs.append({
            "id": f"{KEY}-{clean(d.get('PositionID')) or item.get('MatchedObjectId')}",
            "title": clean(d.get("PositionTitle")) or "Untitled posting",
            "url": d.get("ApplyURI", [d.get("PositionURI")])[0] if d.get("ApplyURI") else d.get("PositionURI"),
            "employer": org,
            "employer_type": "Federal",
            "location": clean(locations),
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
