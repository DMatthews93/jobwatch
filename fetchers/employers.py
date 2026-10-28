"""Generic scraper for employer careers pages listed in config.EMPLOYER_SOURCES.

It looks for links on the page that match the config and treats each as a job. It cannot read
pages that load their jobs with JavaScript; for those, use the employer's feed or API if it has one.
Optional keys per source:
  list_url_regex  the job list is a separate HTML fragment the page loads (e.g. an Astro server
                  island); its address is found in the page with this regex and read instead.
  detail          read each new advert page once for pay, hours, contract and "Location:".
  location        fallback location when the advert doesn't give one.
"""
import html
import re
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

import config
from fetchers.common import SourceSkipped, clean, enrich, get, make_job
from bs4 import BeautifulSoup

CARRY = ("hours_per_week", "full_time", "contract_type", "location", "salary_text", "salary_min", "salary_max",
         "salary_basis", "salary_stated", "salary_converted", "snippet", "detail_done")


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


def _list_page(src):
    """HTML holding the job links: the page itself, or the fragment it loads."""
    r = get(src["url"])
    if not r or not src.get("list_url_regex"):
        return r.text if r else None
    m = re.search(src["list_url_regex"], r.text)
    if not m:
        print(f"  ! {src['name']}: job list address not found on the page")
        return None
    r = get(urljoin(src["url"], html.unescape(m.group(0))))
    return r.text if r else None


def _detail(job, src):
    r = get(job["url"])
    if not r:
        return
    text = BeautifulSoup(r.text, "html.parser").get_text("\n")
    # Cut at brackets / "+": "£25,000 per annum (£14.14/hr) + bonus" must read as annual pay
    m = re.search(r"Location\s*:\s*([^\n|(]{3,80})", text)
    if m:
        job["location"] = clean(m.group(1)).rstrip(".,")
    m = re.search(r"(?:Salary|Pay)\s*:\s*([^\n(+]{3,120})", text)
    if m:
        job["salary_text"] = clean(m.group(1))
    enrich(job, text)
    job["detail_done"] = True


def fetch(known):
    if not config.EMPLOYER_SOURCES:
        raise SourceSkipped("no employer pages configured")
    jobs = {}
    for src in config.EMPLOYER_SOURCES:
        url = src["url"]
        if not _allowed(url):
            print(f"  ! {src['name']}: robots.txt disallows this page, skipping")
            continue
        page = _list_page(src)
        if not page:
            continue
        soup = BeautifulSoup(page, "html.parser")
        found = []
        for a in soup.find_all("a", href=True):
            heading = a.find(re.compile(r"^h[1-6]$"))  # card links also wrap team names etc.
            title, href = clean((heading or a).get_text(" ")), urljoin(url, a["href"])
            if len(title) < 5 or src.get("link_contains", "") not in href:
                continue
            if not re.search(src.get("title_regex", "."), title, re.I) or href in jobs:
                continue
            job = make_job(source="employer", source_id=href, title=title, employer=src["name"],
                           url=href, category=src.get("category", "priv"))
            jobs[href] = enrich(job, title)
            found.append(job)
        for job in found if src.get("detail") else []:
            prev = known.get(("employer", job["source_id"]))
            if prev and prev.get("detail_done"):
                job.update({f: prev[f] for f in CARRY if prev.get(f) is not None})
            else:
                _detail(job, src)
        for job in found:
            job["location"] = job["location"] or src.get("location", "")
        print(f"  employer: {src['name']} -> {len(found)} links")
        if not found:
            print("    (nothing matched; the page may use JavaScript, or link_contains/title_regex need tuning)")
    return list(jobs.values())
