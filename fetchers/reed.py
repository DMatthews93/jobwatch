"""Reed API fetcher. Needs a free API key in the REED_API_KEY secret."""
import os

from fetchers.common import SourceSkipped, enrich, get, make_job, parse_date, strip_html
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
    jobs = {}
    for words, category in config.REED_QUERIES:
        skip = 0
        while skip < config.REED_MAX_RESULTS:
            params = {"keywords": words, "locationName": config.SEARCH_POSTCODE,
                      "distancefromlocation": config.RADIUS_MILES,
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
    return list(jobs.values())
