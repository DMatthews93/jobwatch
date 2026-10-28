"""Add lat/lng to jobs using postcodes.io (free, no key). Results are cached in data/geocache.json."""
import json
import math
import os
import re

import requests

CACHE_FILE = os.path.join("data", "geocache.json")
POSTCODE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b", re.I)
SKIP_PLACES = {"remote", "uk", "united kingdom", "england", "various", "nationwide",
               "home based", "home-based", "hybrid", "anywhere"}
MAX_PLACE_LOOKUPS = 40


def _load():
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(cache):
    os.makedirs("data", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, sort_keys=True, indent=0)


def _postcode_key(location):
    m = POSTCODE.search(location or "")
    return f"pc:{m.group(1).upper()} {m.group(2).upper()}" if m else None


def _place_key(location):
    for part in (location or "").split(","):
        p = part.strip().lower()
        if len(p) > 2 and p not in SKIP_PLACES:
            return f"pl:{p}"
    return None


def _bulk_postcodes(keys, cache):
    pcs = [k[3:] for k in keys]
    for i in range(0, len(pcs), 100):
        chunk = pcs[i:i + 100]
        try:
            r = requests.post("https://api.postcodes.io/postcodes", json={"postcodes": chunk}, timeout=30)
            for item in r.json().get("result") or []:
                res = item.get("result")
                cache["pc:" + item["query"].upper()] = [res["latitude"], res["longitude"]] if res else None
        except (requests.RequestException, ValueError, KeyError):
            print("  ! postcode lookup failed for a batch")


def _place(key, cache):
    try:
        r = requests.get("https://api.postcodes.io/places", params={"q": key[3:], "limit": 1}, timeout=20)
        res = (r.json().get("result") or [None])[0]
        cache[key] = [res["latitude"], res["longitude"]] if res and res.get("latitude") else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        pass  # leave uncached so it is retried next run


def geocode(jobs):
    cache = _load()
    todo = [j for j in jobs if j.get("lat") is None]
    pcs = {k for j in todo if (k := _postcode_key(j["location"])) and k not in cache}
    if pcs:
        _bulk_postcodes(sorted(pcs), cache)
    places = {k for j in todo if not _postcode_key(j["location"]) and (k := _place_key(j["location"])) and k not in cache}
    for k in sorted(places)[:MAX_PLACE_LOOKUPS]:
        _place(k, cache)
    for j in todo:
        hit = cache.get(_postcode_key(j["location"]) or "") or cache.get(_place_key(j["location"]) or "")
        if hit:
            j["lat"], j["lng"] = hit
    _save(cache)
    print(f"  geocoded {sum(1 for j in jobs if j.get('lat') is not None)}/{len(jobs)} jobs")


def home(postcode):
    """lat/lng of the search postcode, or None. Never cached or printed: the repo is public."""
    if not postcode:
        return None
    try:
        r = requests.get("https://api.postcodes.io/postcodes/" + requests.utils.quote(postcode), timeout=20)
        res = r.json().get("result")
        return (res["latitude"], res["longitude"]) if res else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def miles(a, b):
    """Great-circle distance in miles between two (lat, lng) pairs."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    x = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3959 * 2 * math.asin(math.sqrt(x))
