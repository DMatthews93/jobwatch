"""Remember jobs between runs: first_seen, stale/closed status, stable ids."""
import hashlib
from datetime import datetime, timezone

import config


def _passed(closing, today):
    try:
        return datetime.strptime(closing, "%Y-%m-%d").date() < today
    except (TypeError, ValueError):
        return False


def update(prev_jobs, current, failed_sources=(), now=None):
    now = now or datetime.now(timezone.utc)
    today, stamp = now.date(), now.strftime("%Y-%m-%dT%H:%M:%SZ")
    failed = set(failed_sources)
    prev_by_id = {p["id"]: p for p in prev_jobs}
    pair_to_id = {(l["source"], l["source_id"]): p["id"]
                  for p in prev_jobs for l in p.get("links", [])}
    out, used = [], set()
    for job in current:
        jid = next((pair_to_id[(l["source"], l["source_id"])] for l in job["links"]
                    if pair_to_id.get((l["source"], l["source_id"])) not in (None, *used)), None)
        if jid is None:
            jid = hashlib.sha1(f"{job['source']}:{job['source_id']}".encode()).hexdigest()[:12]
        used.add(jid)
        prev = prev_by_id.get(jid)
        job["id"] = jid
        job["first_seen"] = prev["first_seen"] if prev else stamp
        job["missing_since"] = None
        if prev:
            for f in ("hours_per_week", "full_time"):
                if job.get(f) is None and prev.get(f) is not None:
                    job[f] = prev[f]
            if job["contract_type"] == "unknown":
                job["contract_type"] = prev.get("contract_type", "unknown")
        job["status"] = "closed" if _passed(job.get("closing"), today) else "open"
        out.append(job)
    for p in prev_jobs:
        if p["id"] in used:
            continue
        sources = {l["source"] for l in p.get("links", [])}
        if sources and sources <= failed:
            out.append(p)  # its source(s) could not be read this run: change nothing
            continue
        since = p.get("missing_since") or stamp
        days = (today - datetime.strptime(since[:10], "%Y-%m-%d").date()).days
        if days >= config.DROP_DAYS:
            continue
        p = dict(p, missing_since=since)
        p["status"] = "closed" if days >= config.STALE_DAYS or _passed(p.get("closing"), today) else "stale"
        out.append(p)
    return out
