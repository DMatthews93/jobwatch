"""Private hospital groups (config.HOSPITAL_SOURCES), read from the job feeds their careers sites use.

Spire runs Oracle Recruiting Cloud and Ramsay runs Workday; both expose the same public JSON the
careers page itself loads. Only roles matching config.HOSPITAL_ROLES are kept, within the usual radius.
"""
import re
from datetime import date, timedelta

import config
import geo
from fetchers.common import clean, enrich, get, make_job, post

ORACLE_PAGE = 25
WORKDAY_PAGE = 20  # Workday's maximum page size
MAX_PAGES = 40


def role_category(title):
    if re.search(config.HOSPITAL_EXCLUDE, title, re.I):
        return None
    for category, pattern in config.HOSPITAL_ROLES:
        if re.search(pattern, title, re.I):
            return category
    return None


def workday_posted(text, today=None):
    """'Posted Today' / 'Posted Yesterday' / 'Posted 3 Days Ago' -> ISO date. '30+ Days' -> None."""
    today = today or date.today()
    t = (text or "").lower()
    if "today" in t:
        return today.isoformat()
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+) days? ago", t)
    return (today - timedelta(days=int(m.group(1)))).isoformat() if m and "+" not in t else None


def _place(text):
    """'EDINBURGH, MIDLOTHIAN, United Kingdom' -> 'Edinburgh, Midlothian'. '2 Locations' -> ''."""
    if re.match(r"\d+ locations", text or "", re.I):
        return ""
    parts = [p.strip() for p in (text or "").split(",") if p.strip() and p.strip().lower() != "united kingdom"]
    return ", ".join(p.title() if p.isupper() else p for p in parts)


def _oracle(src):
    jobs = []
    for page in range(MAX_PAGES):
        url = (f"{src['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true"
               f"&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber={src['site']},"
               f"limit={ORACLE_PAGE},offset={page * ORACLE_PAGE},sortBy=POSTING_DATES_DESC")
        r = get(url, headers={"Accept": "application/json"})
        if not r:
            break
        items = (r.json().get("items") or [{}])[0].get("requisitionList") or []
        for it in items:
            title = it.get("Title", "")
            category = role_category(title)
            if not category:
                continue
            summary = clean(it.get("ShortDescriptionStr"))
            job = make_job(
                source="hospital", source_id=f"{src['name'].split()[0].lower()}-{it['Id']}", title=title, employer=src["name"],
                url=f"{src['host']}/hcmUI/CandidateExperience/en/sites/{src['site']}/job/{it['Id']}",
                category=category, location=_place(it.get("PrimaryLocation")),
                posted=it.get("PostedDate"), closing=it.get("PostingEndDate"), snippet=summary[:400])
            jobs.append(enrich(job, f"{title}. {summary}"))
        if len(items) < ORACLE_PAGE:
            break
    return jobs


def _workday(src):
    jobs, total = [], None
    api = f"{src['host']}/wday/cxs/{src['tenant']}/{src['site']}/jobs"
    for page in range(MAX_PAGES):
        r = post(api, json={"appliedFacets": {}, "limit": WORKDAY_PAGE, "offset": page * WORKDAY_PAGE,
                            "searchText": ""}, headers={"Accept": "application/json"})
        if not r:
            break
        d = r.json()
        total = total or d.get("total") or 0  # Workday only reports the total on the first page
        items = d.get("jobPostings") or []
        for it in items:
            title = it.get("title", "")
            category = role_category(title)
            if not category:
                continue
            path = it.get("externalPath", "")
            job = make_job(
                source="hospital", source_id=f"{src['tenant']}-{path.rsplit('_', 1)[-1]}", title=title,
                employer=src["name"], url=f"{src['host']}/{src['site']}{path}", category=category,
                location=_place(it.get("locationsText")), posted=workday_posted(it.get("postedOn")))
            jobs.append(enrich(job, f"{title}. {it.get('timeType', '')}"))
        if len(items) < WORKDAY_PAGE or (page + 1) * WORKDAY_PAGE >= total:
            break
    return jobs


def _near_enough(jobs):
    """Same radius rules as Reed: everyday work close to home, medical roles further afield."""
    here = geo.home(config.SEARCH_POSTCODE)
    if not here:
        print("  ! hospitals: could not locate the search postcode, keeping every location")
        return jobs
    geo.geocode(jobs)
    keep = []
    for j in jobs:
        local = j["category"] in config.LOCAL_CATEGORIES
        if j["lat"] is None:
            if not local:  # everyday work is only worth showing when it is known to be nearby
                keep.append(j)
        elif geo.miles(here, (j["lat"], j["lng"])) <= (config.LOCAL_RADIUS_MILES if local else config.RADIUS_MILES):
            keep.append(j)
    return keep


def fetch(known):
    jobs = []
    for src in config.HOSPITAL_SOURCES:
        found = _oracle(src) if src["type"] == "oracle" else _workday(src)
        print(f"  hospitals: {src['name']} -> {len(found)} relevant roles")
        jobs.extend(found)
    near = _near_enough(jobs)
    print(f"  hospitals: {len(near)} of {len(jobs)} within range")
    return near
