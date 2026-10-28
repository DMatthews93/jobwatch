"""Fetch -> flag -> geocode -> merge -> remember -> write site/jobs.json."""
import json
import os
import sys
import traceback
from datetime import datetime, timezone

import config
import geo
import state
from fetchers import adzuna, bmj, employers, hospitals, jobsac, nhs, reed
from fetchers.common import SourceSkipped
from fetchers.flags import flag
from merge import merge

FETCHERS = [("nhs", nhs), ("bmj", bmj), ("reed", reed), ("jobsac", jobsac), ("employer", employers),
            ("hospital", hospitals), ("adzuna", adzuna)]
STATE_FILE = os.path.join("data", "state.json")
OUT_FILE = os.path.join("site", "jobs.json")


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f).get("jobs", [])
    except (OSError, ValueError):
        return []


def save_state(jobs):
    """One job per line so git diffs stay small."""
    os.makedirs("data", exist_ok=True)
    jobs = sorted(jobs, key=lambda j: j["id"])
    with open(STATE_FILE, "w") as f:
        f.write('{"jobs":[\n' + ",\n".join(json.dumps(j, sort_keys=True) for j in jobs) + "\n]}\n")


def main():
    if not config.SEARCH_POSTCODE:
        sys.exit("SEARCH_POSTCODE is not set. Add it as a GitHub Actions secret (Settings > Secrets and variables > Actions).")
    prev = load_state()
    known = {(l["source"], l["source_id"]): p for p in prev for l in p.get("links", [])}
    prev_count = {}
    for p in prev:
        for s in {l["source"] for l in p.get("links", [])}:
            prev_count[s] = prev_count.get(s, 0) + 1

    results, ok, failed, errors = [], [], set(), set()
    for name, module in FETCHERS:
        print(f"[{name}]")
        try:
            jobs = module.fetch(known)
        except SourceSkipped as e:
            print(f"  skipped: {e}")
            failed.add(name)
            continue
        except Exception:
            print(f"  ! {name} failed:")
            traceback.print_exc(limit=2)
            failed.add(name)
            errors.add(name)
            continue
        if not jobs and prev_count.get(name, 0) > 10:
            print(f"  ! {name} returned nothing but had {prev_count[name]} jobs before: treating as a failed run")
            failed.add(name)
            errors.add(name)
            continue
        ok.append(name)
        results.extend(jobs)

    results = [flag(j) for j in results]
    geo.geocode(results)
    current = merge(results)
    final = state.update(prev, current, failed)
    save_state(final)

    for j in final:
        j["snippet"] = (j.get("snippet") or "")[:300]
    nlw_annual = round(config.NLW_HOURLY * config.FULL_TIME_HOURS * 52)
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settings": {"nlw_hourly": config.NLW_HOURLY, "full_time_hours": config.FULL_TIME_HOURS,
                     "nlw_full_time_annual": nlw_annual},
        "sources": {"ok": ok, "not_updated": sorted(errors)},
        "jobs": final,
    }
    os.makedirs("site", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    open_n = sum(1 for j in final if j["status"] == "open")
    print(f"Done: {len(final)} jobs ({open_n} open). Sources ok: {ok}. Not updated: {sorted(failed)}")


if __name__ == "__main__":
    main()
