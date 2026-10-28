"""jobs.ac.uk RSS fetcher (research and academic posts)."""
import re
import xml.etree.ElementTree as ET

import config
from fetchers.common import SourceSkipped, enrich, get, make_job, parse_date, strip_html


def _after(label, text, stops):
    m = re.search(rf"{label}:\s*(.+?)\s*(?:{'|'.join(stops)}|$)", text, re.I)
    return m.group(1).strip() if m else ""


def fetch(known):
    if not config.JOBSAC_FEEDS:
        raise SourceSkipped("no jobs.ac.uk feeds configured")
    jobs, readable = {}, 0
    for url, category in config.JOBSAC_FEEDS:
        r = get(url)
        if not r:
            continue
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            print("  ! jobs.ac.uk: that address did not return an RSS feed. Check JOBSAC_FEEDS in config.py")
            continue
        readable += 1
        for item in root.iter("item"):
            link = (item.findtext("link") or "").strip()
            title = strip_html(item.findtext("title") or "")
            desc = strip_html(item.findtext("description") or "")
            if not link or link in jobs:
                continue
            if not re.search(config.JOBSAC_KEYWORDS, f"{title} {desc}", re.I):
                continue
            stops = ["Location:", "Salary:", "Employer:", "Closes:", "Closing"]
            employer = _after("Employer", desc, stops)
            if not employer and "," in title:
                title, employer = title.rsplit(",", 1)
            job = make_job(
                source="jobsac", source_id=link.rstrip("/").rsplit("/", 1)[-1], title=title,
                employer=employer or "Unknown employer", url=link, category=category,
                location=_after("Location", desc, stops),
                posted=parse_date(item.findtext("pubDate")),
                closing=parse_date(_after("Clos(?:es|ing)(?: date)?", desc, stops)),
                snippet=desc[:400], salary_text=_after("Salary", desc, stops),
            )
            jobs[link] = enrich(job, f"{title}. {desc}")
    if not readable:
        raise RuntimeError("no jobs.ac.uk feed could be read")
    print(f"  jobsac: {len(jobs)} jobs")
    return list(jobs.values())
