"""Reed API fetcher. Needs a free API key in the REED_API_KEY secret."""
import os
import re
from datetime import datetime, timezone

import geo
from fetchers.common import SourceSkipped, clean, enrich, get, make_job, parse_date, strip_html
import config

API = "https://www.reed.co.uk/api/1.0/search"


def _salary_text(item):
    lo, hi = item.get("minimumSalary"), item.get("maximumSalary")
    if not (lo or hi):
        return ""
    return f"£{lo or hi:g} to £{hi or lo:g}"


def fetch(known):
    key = os.getenv("REED_API_KEY", "").strip()
    if not key:
        raise SourceSkipped("REED_API_KEY not set")
    now = datetime.now(timezone.utc)
    if not os.getenv("FORCE_FETCH") and config.REED_EVERY_HOURS > 1 and (
            now.hour % config.REED_EVERY_HOURS or now.minute >= 30):
        raise SourceSkipped("not Reed's turn this run (runs every few hours)")
    jobs = {}
    for words, category in config.REED_QUERIES:
        skip = 0
        while skip < config.REED_MAX_RESULTS:
            params = {"keywords": words, "locationName": config.SEARCH_POSTCODE,
                      "distancefromlocation": config.LOCAL_RADIUS_MILES if category in config.LOCAL_CATEGORIES else config.RADIUS_MILES,
                      "resultsToTake": 100, "resultsToSkip": skip}
            if config.REED_FULL_TIME_ONLY:
                params["fullTime"] = "true"
            r = get(API, params=params, auth=(key, ""))
            if not r:
                break
            results = r.json().get("results") or []
            for it in results:
                jid = str(it.get("jobId"))
                if jid in jobs:
                    continue
                job = make_job(
                    source="reed", source_id=jid, title=it.get("jobTitle", ""),
                    employer=it.get("employerName", ""), url=it.get("jobUrl", ""),
                    category=category, location=it.get("locationName", ""),
                    posted=parse_date(it.get("date")), closing=parse_date(it.get("expirationDate")),
                    snippet=strip_html(it.get("jobDescription", ""))[:400],
                    salary_text=_salary_text(it),
                    full_time=True if config.REED_FULL_TIME_ONLY else None,
                )
                jobs[jid] = enrich(job, f"{job['title']}. {job['snippet']}")
            if len(results) < 100:
                break
            skip += 100
        print(f"  reed: '{words}' -> {len(jobs)} jobs so far")
    _use_stated_locations(list(jobs.values()))
    return list(jobs.values())


_STATED = re.compile(r"\bLocation\s*:\s*(.{2,60}?)(?=\s+(?:Pay|Salary|Rate|Shift|Hours|Job Type|Contract|"
                     r"Working|Start|Closing|Duration)\b|[.;|(\n]|$)", re.I)


def stated_location(text):
    """'... Location: Orkney Pay: 18 per hour ...' -> 'Orkney'."""
    m = _STATED.search(text or "")
    return clean(m.group(1)) if m else ""


def _use_stated_locations(jobs):
    """Reed's location is sometimes the recruiter's office (NE1 for a job in Orkney). When the advert
    states a location that is found and is far from Reed's, trust the advert."""
    pairs = [(j, {"location": s, "lat": None, "lng": None}) for j in jobs if (s := stated_location(j["snippet"]))]
    if not pairs:
        return
    geo.geocode([j for j, _ in pairs] + [s for _, s in pairs])
    moved = 0
    for j, s in pairs:
        if j["lat"] is not None and s["lat"] is not None and \
                geo.miles((j["lat"], j["lng"]), (s["lat"], s["lng"])) > config.STATED_LOCATION_MILES:
            j["location"], j["lat"], j["lng"] = s["location"], s["lat"], s["lng"]
            moved += 1
    print(f"  reed: {moved} jobs moved to the location stated in the advert")
