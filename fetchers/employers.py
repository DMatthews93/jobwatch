"""Generic scraper for employer careers pages listed in config.EMPLOYER_SOURCES.

It looks for links on the page that match the config and treats each as a job. It cannot read
pages that load their jobs with JavaScript; for those, use the employer's feed or API if it has one.
"""
import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

import config
from fetchers.common import SourceSkipped, clean, enrich, get, make_job
from bs4 import BeautifulSoup


def _allowed(url):
    p = urlparse(url)
    try:
        r = requests.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=15,
                         headers={"User-Agent": config.USER_AGENT})
        if r.status_code != 200:
            return True
        rp = RobotFileParser()
        rp.parse(r.text.splitlines())
        return rp.can_fetch(config.USER_AGENT, url)
    except requests.RequestException:
        return True


def fetch(known):
    if not config.EMPLOYER_SOURCES:
        raise SourceSkipped("no employer pages configured")
    jobs = {}
    for src in config.EMPLOYER_SOURCES:
        url = src["url"]
        if not _allowed(url):
            print(f"  ! {src['name']}: robots.txt disallows this page, skipping")
            continue
        r = get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        found = 0
        for a in soup.find_all("a", href=True):
            title, href = clean(a.get_text(" ")), urljoin(url, a["href"])
            if len(title) < 5 or src.get("link_contains", "") not in href:
                continue
            if not re.search(src.get("title_regex", "."), title, re.I) or href in jobs:
                continue
            job = make_job(source="employer", source_id=href, title=title, employer=src["name"],
                           url=href, category=src.get("category", "priv"))
            jobs[href] = enrich(job, title)
            found += 1
        print(f"  employer: {src['name']} -> {found} links")
        if found == 0:
            print("    (nothing matched; the page may use JavaScript, or link_contains/title_regex need tuning)")
    return list(jobs.values())
