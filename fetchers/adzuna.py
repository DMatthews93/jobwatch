"""Adzuna fetcher. PAID API, so it is OFF unless ENABLE_ADZUNA=true and keys are set.

When on, it only runs once every few hours to stay inside the monthly call allowance.
"""
import os
from datetime import datetime, timezone

import config
from fetchers.common import SourceSkipped, enrich, get, make_job, parse_date, strip_html

API = "https://api.adzuna.com/v1/api/jobs/gb/search/1"


def fetch(known):
    if os.getenv("ENABLE_ADZUNA", "").lower() not in ("1", "true", "yes"):
        raise SourceSkipped("Adzuna is switched off (paid API)")
    app_id, app_key = os.getenv("ADZUNA_APP_ID", ""), os.getenv("ADZUNA_APP_KEY", "")
    if not (app_id and app_key):
        raise SourceSkipped("ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
    now = datetime.now(timezone.utc)
    if now.hour % config.ADZUNA_EVERY_HOURS or now.minute >= 30:
        raise SourceSkipped("not Adzuna's turn this run")
    jobs = {}
    for words, category in config.REED_QUERIES:
        params = {"app_id": app_id, "app_key": app_key, "what": words,
                  "where": config.SEARCH_POSTCODE, "distance": round(config.RADIUS_MILES * 1.609),
                  "results_per_page": 50, "full_time": 1}
        r = get(API, params=params)
        if not r:
            continue
        for it in r.json().get("results") or []:
            jid = str(it.get("id"))
            if jid in jobs:
                continue
            predicted = str(it.get("salary_is_predicted")) == "1"
            lo, hi = it.get("salary_min"), it.get("salary_max")
            job = make_job(
                source="adzuna", source_id=jid, title=it.get("title", ""),
                employer=(it.get("company") or {}).get("display_name", ""),
                url=it.get("redirect_url", ""), category=category,
                location=(it.get("location") or {}).get("display_name", ""),
                lat=it.get("latitude"), lng=it.get("longitude"),
                posted=parse_date(it.get("created")), snippet=strip_html(it.get("description", ""))[:400],
                salary_text=f"£{lo:g} to £{hi:g} a year" if lo and hi else "",
                full_time=True if it.get("contract_time") == "full_time" else None,
                salary_estimated=predicted,
            )
            ct = (it.get("contract_type") or "").lower()
            if ct in ("permanent", "contract"):
                job["contract_type"] = "permanent" if ct == "permanent" else "fixed-term"
            jobs[jid] = enrich(job, f"{job['title']}. {job['snippet']}")
    print(f"  adzuna: {len(jobs)} jobs")
    return list(jobs.values())
