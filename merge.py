"""Merge the same job found on several sources into one card with several apply links."""
import re
from datetime import date
from difflib import SequenceMatcher

PRIORITY = {"nhs": 0, "employer": 1, "reed": 2, "jobsac": 3, "adzuna": 4}
_STOP = {"the", "of", "and", "nhs", "foundation", "trust", "ft", "ltd", "limited", "plc", "uk", "group"}


def _words(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower().replace("&", " and ")).split()


def norm_employer(s):
    return " ".join(w for w in _words(s) if w not in _STOP)


def norm_title(s):
    return " ".join(_words(s))


def _ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


def _days_apart(a, b):
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except (TypeError, ValueError):
        return 0


def is_dup(a, b):
    ea, eb = norm_employer(a["employer"]), norm_employer(b["employer"])
    if not ea or not eb or _ratio(ea, eb) < 0.8:
        return False
    if _ratio(norm_title(a["title"]), norm_title(b["title"])) < 0.88:
        return False
    la, lb = norm_title(a["location"]), norm_title(b["location"])
    if la and lb and la not in lb and lb not in la and _ratio(la, lb) < 0.6:
        return False
    return _days_apart(a.get("closing"), b.get("closing")) <= 14


def _combine(group):
    p = dict(group[0])
    p["links"], seen = [], set()
    for m in group:
        if m["url"] and m["url"] not in seen:
            seen.add(m["url"])
            p["links"].append({"source": m["source"], "source_id": m["source_id"], "url": m["url"]})
    for m in group[1:]:
        for f in ("lat", "lng", "closing", "location", "snippet", "hours_per_week", "full_time"):
            if p.get(f) in (None, ""):
                p[f] = m.get(f)
        if p["contract_type"] == "unknown":
            p["contract_type"] = m["contract_type"]
        better = m["salary_stated"] and (not p["salary_stated"] or (p["salary_estimated"] and not m["salary_estimated"]))
        if better:
            for f in ("salary_text", "salary_min", "salary_max", "salary_basis", "salary_stated",
                      "salary_converted", "salary_estimated"):
                p[f] = m[f]
        if m.get("posted") and (not p.get("posted") or m["posted"] < p["posted"]):
            p["posted"] = m["posted"]
        p["flags"] = sorted(set(p["flags"]) | set(m["flags"]))
        p["tags"] = sorted(set(p["tags"]) | set(m["tags"]))
        p["detail_done"] = p["detail_done"] or m["detail_done"]
    p["sources"] = sorted({m["source"] for m in group})
    return p


def merge(jobs):
    buckets, groups = {}, []
    for j in sorted(jobs, key=lambda x: PRIORITY.get(x["source"], 9)):
        words = norm_employer(j["employer"]).split()
        key = words[0] if words else ""
        for g in buckets.get(key, []):
            if is_dup(g[0], j):
                g.append(j)
                break
        else:
            g = [j]
            groups.append(g)
            buckets.setdefault(key, []).append(g)
    return [_combine(g) for g in groups]
