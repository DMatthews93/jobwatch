"""NHS Jobs fetcher: scrapes the public search results (same approach as the old job_checker.py)."""
import re

from bs4 import BeautifulSoup, NavigableString

import config
from fetchers.flags import flag
from fetchers.common import clean, enrich, get, infer_contract, make_job, parse_date, parse_hours

SEARCH_URL = "https://www.jobs.nhs.uk/candidate/search/results"
CARRY = ("hours_per_week", "full_time", "contract_type", "detail_done")


def _normalize_url(url):
    m = re.search(r"/jobadvert/([a-zA-Z0-9\-]+)", url)
    return f"https://www.jobs.nhs.uk/candidate/jobadvert/{m.group(1).upper()}" if m else url


def _text(card, selector):
    tag = card.select_one(selector)
    return clean(tag.get_text(" ")) if tag else ""


def _parse_card(card):
    a = card.select_one("h2 a[data-test='search-result-job-title']")
    if not a:
        return None
    url = _normalize_url("https://www.jobs.nhs.uk" + a["href"])
    h3 = card.select_one("div[data-test='search-result-location'] h3")
    employer = ""
    if h3:
        employer = next((str(c).strip() for c in h3.contents
                         if isinstance(c, NavigableString) and str(c).strip()), "")
    loc = card.select_one("div[data-test='search-result-location'] h3 div")
    job = make_job(
        source="nhs", source_id=url.rsplit("/", 1)[-1], title=a.get_text(strip=True),
        employer=employer, url=url, category="nhs",
        location=clean(loc.get_text(" ")) if loc else "",
        posted=parse_date(_text(card, "li[data-test='search-result-publicationDate'] strong")),
        closing=parse_date(_text(card, "li[data-test='search-result-closingDate'] strong")),
        snippet=_text(card, "div.nhsuk-u-margin-bottom-4")[:400],
        salary_text=_text(card, "li[data-test='search-result-salary'] strong"),
    )
    if any(p in employer.lower() for p in config.PRIVATE_PROVIDERS):
        job["category"] = "priv"
    return job


def _grab(text, label):
    m = re.search(rf"{label}[ \t]*:?[ \t]*\n*\s*([^\n]+)", text, re.I)
    return clean(m.group(1)) if m else ""


def _detail(url):
    r = get(url)
    if not r:
        return None
    text = BeautifulSoup(r.text, "html.parser").get_text("\n")
    return {"contract": _grab(text, "Contract type"), "pattern": _grab(text, "Working pattern")}


def fetch(known):
    jobs = {}
    searches = [(kw, True) for kw in config.NHS_KEYWORDS] + [(kw, False) for kw in config.NHS_EXTRA_KEYWORDS]
    for kw, narrow in searches:
        for page in range(1, config.NHS_MAX_PAGES + 1):
            params = {"keyword": kw, "location": config.SEARCH_POSTCODE,
                      "skipPhraseSuggester": "true", "distance": config.RADIUS_MILES,
                      "language": "en", "page": page}
            if narrow:
                params["staffGroup"] = config.NHS_STAFF_GROUP
                params["payBand"] = ",".join(config.NHS_PAY_BANDS)
            r = get(SEARCH_URL, params=params)
            if not r:
                break
            cards = BeautifulSoup(r.text, "html.parser").find_all("li", {"data-test": "search-result"})
            if not cards:
                break
            for card in cards:
                try:
                    job = _parse_card(card)
                except Exception as e:  # one odd card must not kill the run
                    print(f"  ! could not parse a card: {type(e).__name__}")
                    continue
                if job and job["url"] not in jobs:
                    jobs[job["url"]] = enrich(job, f"{job['title']}. {job['snippet']}")
        print(f"  nhs: '{kw}' -> {len(jobs)} jobs so far")

    # Hours / contract type live on the advert page: fetch each new advert once, then remember it.
    fetched = 0
    for job in jobs.values():
        prev = known.get(("nhs", job["source_id"]))
        if prev and prev.get("detail_done"):
            for f in CARRY:
                if prev.get(f) is not None:
                    job[f] = prev[f]
            continue
        flag(job)
        if {"non-doctor-role", "other-specialty"} & set(job["flags"]):
            continue  # don't spend a page fetch on roles the site hides by default
        if fetched >= config.MAX_DETAIL_PER_RUN:
            continue
        fetched += 1
        d = _detail(job["url"])
        if d is None:
            continue
        hours, ft = parse_hours(d["pattern"])
        if hours:
            job["hours_per_week"] = hours
        if ft is not None:
            job["full_time"] = ft
        c = infer_contract(d["contract"])
        if c != "unknown":
            job["contract_type"] = c
        job["detail_done"] = True
    print(f"  nhs: {len(jobs)} jobs, {fetched} advert pages read")
    return list(jobs.values())
