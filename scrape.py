#!/usr/bin/env python3
"""Run every source, merge the results, and write docs/jobs.json.

Each source is run independently: if one site is down or changes its markup,
the others still produce output. Run it with:  python scrape.py
"""
import datetime
import json
import os

from sources import parc, tamu, usajobs_fws, afwa, reliefweb

SOURCES = [parc, tamu, usajobs_fws, afwa, reliefweb]
OUT_PATH = os.path.join(os.path.dirname(__file__), "docs", "jobs.json")


def dedupe(jobs):
    """Drop duplicates, preferring the first seen. Key on apply URL, then
    on a normalized title+employer pair."""
    seen, unique = set(), []
    for job in jobs:
        url = (job.get("url") or "").strip().lower().rstrip("/")
        title = (job.get("title") or "").strip().lower()
        employer = (job.get("employer") or "").strip().lower()
        key = url or f"{title}@@{employer}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def sort_key(job):
    """Soonest real deadline first; undated postings sink to the bottom."""
    return job.get("deadline") or "9999-12-31"


def main():
    all_jobs, status = [], {}
    for module in SOURCES:
        name = getattr(module, "NAME", module.__name__)
        try:
            found = module.scrape()
            all_jobs.extend(found)
            status[module.KEY] = {"name": name, "count": len(found), "ok": True}
            print(f"  [{module.KEY}] {len(found)} postings")
        except Exception as exc:  # one bad source shouldn't sink the run
            status[module.KEY] = {"name": name, "count": 0, "ok": False, "error": str(exc)}
            print(f"  [{module.KEY}] FAILED — {exc}")

    jobs = sorted(dedupe(all_jobs), key=sort_key)
    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "count": len(jobs),
        "sources": status,
        "jobs": jobs,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(jobs)} postings -> {OUT_PATH}")


if __name__ == "__main__":
    main()
