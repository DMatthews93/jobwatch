"""BMJ Careers fetcher: reads the official RSS feeds listed in config.BMJ_FEEDS.

Each feed item gives title, employer, pay, a short summary and the town. Hours, contract type and
the postcode are only on the advert page, so each new advert is read once and then remembered.
"""
import json
import re
import time
import xml.etree.ElementTree as ET

import config
from fetchers.common import clean, enrich, get, infer_contract, make_job, parse_date, parse_hours

FEED = "https://www.bmj.com/careers/jobsrss/?Profession={}&LocationId=164&countrycode=GB"
CARRY = ("hours_per_week", "full_time", "contract_type", "location", "detail_done")
PRIVATE_EMPLOYER = re.compile(r"\bltd\b|\blimited\b|\bplc\b|\bllp\b|\bclinic\b|\bprivate\b", re.I)

_last_request = 0.0


def _get(url):
    """get() spaced out to honour bmj.com's crawl delay."""
    global _last_request
    wait = _last_request + config.BMJ_DELAY - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()
    return get(url)


def parse_item(title, description, link, category):
    """Turn one RSS item into a job. Description lines: pay:, employer:, summary, town."""
    lines = [l.strip() for l in (description or "").splitlines() if l.strip()]
    m = re.search(r"/careers/job/(\d+)/([^/?]+)", link or "")
    if not m or len(lines) < 2:
        return None
    pay = lines[0].rstrip(":").strip()
    employer = lines[1].rstrip(":").strip()
    summary = " ".join(lines[2:-1]) if len(lines) > 3 else ""
    town = lines[-1] if len(lines) > 2 else ""
    if not title.startswith(employer + ":"):
        return None  # real adverts are "Employer: Title"; anything else is a BMJ notice
    title = title[len(employer) + 1:]
    if category == "nhs" and "nhs" not in employer.lower() and (
            PRIVATE_EMPLOYER.search(employer) or any(p in employer.lower() for p in config.PRIVATE_PROVIDERS)):
        category = "priv"
    job = make_job(source="bmj", source_id=m.group(1), title=title, employer=employer,
                   url=f"https://www.bmj.com/careers/job/{m.group(1)}/{m.group(2)}/",
                   category=category, location=town, snippet=clean(summary)[:400], salary_text=pay)
    return enrich(job, f"{job['title']}. {pay}. {summary}")


def parse_detail(html):
    """Hours, contract and postcode from the advert page's analytics data block."""
    out = {}
    for key, field in (("Hours", "hours"), ("Contract Type", "contract"), ("Location", "postcode")):
        m = re.search(rf'"{re.escape(key)}"\s*:\s*("(?:[^"\\]|\\.)*")', html)
        if m:
            out[field] = clean(json.loads(m.group(1)))
    return out


def _add_detail(job, d):
    hours, ft = parse_hours(d.get("hours", ""))
    if hours:
        job["hours_per_week"] = hours
    if ft is not None:
        job["full_time"] = ft
    c = infer_contract(d.get("contract", "").replace("Fixed Contract", "fixed-term"))
    if c != "unknown":
        job["contract_type"] = c
    pc = d.get("postcode", "")
    if re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}", pc, re.I) and pc.upper() not in job["location"].upper():
        job["location"] = f"{job['location']}, {pc.upper()}".lstrip(", ")
    job["detail_done"] = True


def fetch(known):
    jobs = {}
    for profession, category in config.BMJ_FEEDS:
        r = _get(FEED.format(profession))
        if not r:
            continue
        for it in ET.fromstring(r.content).iter("item"):
            job = parse_item(it.findtext("title") or "", it.findtext("description") or "",
                             it.findtext("link") or "", category)
            if job and job["source_id"] not in jobs:
                job["posted"] = parse_date(it.findtext("pubDate"))
                jobs[job["source_id"]] = job
        print(f"  bmj: profession {profession} -> {len(jobs)} jobs so far")

    read = 0
    for job in jobs.values():
        prev = known.get(("bmj", job["source_id"]))
        if prev and prev.get("detail_done"):
            for f in CARRY:
                if prev.get(f) is not None:
                    job[f] = prev[f]
            continue
        if read >= config.BMJ_MAX_DETAIL:
            continue
        read += 1
        page = _get(job["url"])
        if page:
            _add_detail(job, parse_detail(page.text))
    print(f"  bmj: {len(jobs)} jobs, {read} advert pages read")
    return list(jobs.values())
