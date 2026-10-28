"""Shared helpers: HTTP, text cleaning, salary/hours parsing, and the job shape."""
import html
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests

import config


class SourceSkipped(Exception):
    """A fetcher deliberately did nothing (no key, disabled, not its turn)."""


_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT


def get(url, retries=3, **kw):
    """GET with retries. Never logs the query string (it can contain the postcode)."""
    kw.setdefault("timeout", 30)
    shown = url.split("?")[0]
    for attempt in range(retries):
        try:
            r = _session.get(url, **kw)
        except requests.RequestException as e:
            print(f"  ! request error for {shown}: {type(e).__name__}")
            time.sleep(2 ** (attempt + 1))
            continue
        if r.status_code == 200:
            time.sleep(config.REQUEST_DELAY)
            return r
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** (attempt + 1))
            continue
        print(f"  ! HTTP {r.status_code} for {shown}")
        return None
    print(f"  ! gave up on {shown}")
    return None


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(str(s or ""))).strip()


def strip_html(s):
    return clean(re.sub(r"<[^>]+>", " ", html.unescape(str(s or ""))))


_DATE_FORMATS = ("%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S")


def parse_date(s):
    s = clean(s)
    if not s:
        return None
    for f in _DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        return None


# --- Salary ------------------------------------------------------------------
_MONEY = re.compile(r"£\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", re.I)
_K_RANGE = re.compile(r"£\s*(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*£?\s*(\d+(?:\.\d+)?)\s*k\b", re.I)
_BASIS = [
    ("hourly", r"per hour|an hour|/ ?h(?:ou)?r\b|\bp/?h\b|hourly"),
    ("daily", r"per day|a day|daily|day rate|/ ?day|per diem"),
    ("weekly", r"per week|a week|weekly|/ ?week"),
    ("monthly", r"per month|a month|monthly|/ ?month"),
    ("annual", r"per annum|a year|annual|\bp\.?a\b|/ ?year|per year"),
]
_TO_ANNUAL = {"annual": 1, "hourly": None, "daily": 260, "weekly": 52, "monthly": 12}


def parse_salary(text, hours=None):
    """Turn advert pay text into annual full-time-equivalent numbers."""
    out = {"salary_min": None, "salary_max": None, "salary_basis": None,
           "salary_stated": False, "salary_converted": False}
    t = (text or "").lower().replace("\xa0", " ")
    k = _K_RANGE.search(t)
    if k:
        nums = [float(k.group(1)) * 1000, float(k.group(2)) * 1000]
    else:
        nums = [float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
                for m in _MONEY.finditer(t)]
    if not nums:
        return out
    lo, hi = (min(nums[:2]), max(nums[:2])) if len(nums) > 1 else (nums[0], nums[0])
    basis = next((name for name, pat in _BASIS if re.search(pat, t)), None)
    if basis is None:
        basis = "hourly" if hi < 100 else "daily" if hi < 1000 else "annual"
    mult = _TO_ANNUAL[basis] or (hours or config.FULL_TIME_HOURS) * 52
    lo, hi = round(lo * mult), round(hi * mult)
    if hi < 5000 or lo > 1_000_000:
        return out
    out.update(salary_min=lo, salary_max=hi, salary_basis=basis,
               salary_stated=True, salary_converted=basis != "annual")
    return out


# --- Hours and contract ------------------------------------------------------
def parse_hours(text):
    """Return (hours_per_week or None, full_time True/False/None)."""
    t = (text or "").lower()
    m = (re.search(r"(\d{1,2}(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:per|a|/|each)\s*(?:week|wk)", t)
         or re.search(r"(\d{1,2}(?:\.\d+)?)\s*(?:hours?|hrs?)\s*/\s*wk", t))
    if m:
        h = float(m.group(1))
        if 4 <= h <= 80:
            return h, h >= 35
    ft = bool(re.search(r"full[- ]?time", t))
    pt = bool(re.search(r"part[- ]?time", t))
    if ft and not pt:
        return None, True
    if pt and not ft:
        return None, False
    return None, None


def infer_contract(text):
    t = (text or "").lower()
    found = set()
    if re.search(r"\blocum\b", t):
        found.add("locum")
    if re.search(r"\bbank\b", t):
        found.add("bank")
    if re.search(r"fixed[- ]term|temporary", t):
        found.add("fixed-term")
    if re.search(r"\bpermanent\b", t):
        found.add("permanent")
    return found.pop() if len(found) == 1 else "unknown"


# --- Job shape -----------------------------------------------------------------
def make_job(source, source_id, title, employer, url, category, **kw):
    job = {
        "source": source, "source_id": str(source_id), "title": clean(title),
        "employer": clean(employer), "location": "", "lat": None, "lng": None,
        "category": category, "url": url, "posted": None, "closing": None, "snippet": "",
        "salary_text": "", "salary_min": None, "salary_max": None, "salary_basis": None,
        "salary_stated": False, "salary_converted": False, "salary_estimated": False,
        "hours_per_week": None, "full_time": None, "contract_type": "unknown",
        "flags": [], "tags": [], "detail_done": False,
    }
    job.update({k: v for k, v in kw.items() if k in job})
    return job


def _salary_snippet(text):
    m = re.search(r"(?:salary|pay|rate)[^£\n]{0,40}(£[^.\n]{0,60})", text or "", re.I)
    return m.group(1) if m else ""


def enrich(job, text=""):
    """Fill missing hours / contract / salary from free text."""
    h, ft = parse_hours(text)
    if job["hours_per_week"] is None and h:
        job["hours_per_week"] = h
    if job["full_time"] is None and ft is not None:
        job["full_time"] = ft
    if job["contract_type"] == "unknown":
        job["contract_type"] = infer_contract(text)
    if not job["salary_stated"]:
        job.update(parse_salary(job["salary_text"] or _salary_snippet(text), job["hours_per_week"]))
    return job
