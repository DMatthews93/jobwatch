"""Label jobs instead of silently dropping them. The site decides what to hide."""
import re

import config


def flag(job):
    title = job["title"].lower()
    text = f"{title} {job['snippet']}".lower()
    flags, tags = set(job.get("flags", [])), set(job.get("tags", []))
    if config.OG_PATTERN.search(text):
        tags.add("O&G")
    if config.ENTRY_PATTERN.search(text):
        tags.add("entry-level")
    if job["category"] in ("nhs", "priv", "aes"):
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in config.NON_DOCTOR_WORDS):
            flags.add("non-doctor-role")
    if job["category"] in ("nhs", "priv"):
        # other-specialty only counts when it is in the TITLE and the job is not O&G
        if "O&G" not in tags and any(re.search(p, title) for p in config.OTHER_SPECIALTY_PATTERNS):
            flags.add("other-specialty")
    if any(re.search(p, text) for p in config.EXPERIENCE_PATTERNS):
        flags.add("needs-nhs-experience")
    job["flags"], job["tags"] = sorted(flags), sorted(tags)
    return job
