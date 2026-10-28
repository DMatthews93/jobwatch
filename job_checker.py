import os
import json
import re
import time
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from datetime import datetime
import requests

# ================= Configuration =================
WEBHOOK_OBGYN = os.getenv("DISCORD_WEBHOOK_OBGYN")  # O&G channel
WEBHOOK_ENTRY = os.getenv("DISCORD_WEBHOOK_ENTRY")  # Entry-level channel

LOCATION = "SR8 1JB"
RADIUS_MILES = 150
SEEN_FILE = "seen_jobs.json"

# ================= Keywords =================
SEARCH_KEYWORDS = [
    "obstetrics", "gynaecology", "obs & gynae", "o&g", "pregnancy",
    "trust grade", "trust doctor", "FY1", "FY2", "SHO",
    "foundation doctor", "core trainee", "obstetrics and gynaecology", "women's health", 
    "clinical fellow",  "junior clinical fellow", "senior clinical fellow",
    "resident doctor", "LAS", "MTI", "locally employed doctor"
]

# Skip non-relevant roles
SKIP_KEYWORDS = [
    "midwife", "administrative", "admin", "nurse", "midwifery",
    "assistant", "ward clerk", "receptionist", "fellowship in",
    "training programme director"
]

# Exclude other medical specialties
EXCLUDE_PATTERNS = [
    r"\bhistopathology\b", r"\bcardiopulmonary\b", r"\btransplantation\b",
    r"\bcardiology\b", r"\boncology\b", r"\banaesth\w*\b", r"\bintensive care\b",
    r"\bcritical care\b", r"\bdental\b", r"\bemergency medicine\b", r"\bophthalmology\b",
    r"\bpaediatrics\b", r"\bradiology\b", r"\bpathology\b", r"\bpsychiatry\b",
    r"\bgeriatrics\b", r"\bneurology\b", r"\burology\b", r"\borthopaedics\b",
    r"\bENT\b", r"\bdermatology\b", r"\bGIM\b", r"\bvascular\b", r"\bGP\b",
    r"\bnephrology\b", r"\bhaematology\b", r"\brheumatology\b", r"\bgastroenterology\b",
    r"\bspinal\b", r"\bplastic surgery\b", r"\bcolorectal\b", r"\brespiratory\b",
    r"\bthoracic\b", r"\brenal\b", r"\bcardiothoracic\b", r"\bchildren\b",
    r"\bneuro\b"
]

# Staff group / pay bands
STAFF_GROUP = "MEDICAL_AND_DENTAL"
PAY_BANDS = [
    "SPECIALTY_DOCTOR", "FOUNDATION_DOCTOR", "SPECIALTY_REGISTRAR",
    "DOCTOR_OTHER", "SPECIALIST"
]

# Skip NHS experience toggle from environment
SKIP_EXPERIENCE = os.getenv("SKIP_EXPERIENCE", "False").lower() in ("true", "1", "yes")
EXPERIENCE_PATTERNS = [
    r"2\s+years?\s+nhs\s+experience",
    r"two\s+years?\s+nhs\s+experience",
    r"previous\s+nhs\s+experience\s+(essential|required)"
]

# ================= Helper Functions =================
def normalize_job_url(url: str) -> str:
    match = re.search(r"/jobadvert/([a-zA-Z0-9\-]+)", url)
    if match:
        job_id = match.group(1).upper()
        return f"https://www.jobs.nhs.uk/candidate/jobadvert/{job_id}"
    return url

def load_seen():
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, "r") as f:
                data = json.load(f)
                seen = set(data) if isinstance(data, list) else set()
                print(f"🔹 Loaded {len(seen)} previously seen jobs")
                return seen
    except Exception as e:
        print(f"⚠️ Failed to load seen_jobs.json ({e})")
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)
    print(f"💾 Saved {len(seen)} jobs to seen file")

def parse_date_string(date_str: str):
    try:
        return datetime.strptime(date_str.strip(), "%d %B %Y")
    except Exception:
        return None

# ================= Fetch Jobs =================
def fetch_jobs():
    all_jobs = []
    seen_links = set()
    pay_band_query = "%2C".join(PAY_BANDS)

    for keyword in SEARCH_KEYWORDS:
        search_query = quote_plus(keyword)
        location_query = quote_plus(LOCATION)
        base_url = (
            f"https://www.jobs.nhs.uk/candidate/search/results?"
            f"keyword={search_query}&"
            f"location={location_query}&"
            f"skipPhraseSuggester=true&"
            f"distance={RADIUS_MILES}&"
            f"staffGroup={STAFF_GROUP}&"
            f"payBand={pay_band_query}&"
            f"language=en"
        )
        page = 1
        while True:
            url = f"{base_url}&page={page}"
            print(f"🔍 Fetching '{keyword}' - page {page}")
            response = requests.get(url)
            if response.status_code != 200:
                print(f"⚠️ Failed to fetch page {page}, status {response.status_code}")
                break
            soup = BeautifulSoup(response.text, "html.parser")
            job_cards = soup.find_all("li", {"data-test": "search-result"})
            if not job_cards:
                break
            for card in job_cards:
                try:
                    title_tag = card.select_one("h2 a[data-test='search-result-job-title']")
                    title = title_tag.get_text(strip=True)
                    link = normalize_job_url("https://www.jobs.nhs.uk" + title_tag["href"])
                    if link in seen_links:
                        continue
                    trust_tag = card.select_one("div[data-test='search-result-location'] h3")
                    trust = trust_tag.contents[0].strip() if trust_tag else ""
                    distance_tag = card.select_one("li[data-test='search-result-distance'] strong")
                    distance = distance_tag.get_text(strip=True) if distance_tag else ""
                    posted_tag = card.select_one("li[data-test='search-result-publicationDate'] strong")
                    posted = posted_tag.get_text(strip=True) if posted_tag else ""
                    closing_tag = card.select_one("li[data-test='search-result-closingDate'] strong")
                    closing = closing_tag.get_text(strip=True) if closing_tag else "Unknown"
                    salary_tag = card.select_one("li[data-test='search-result-salary'] strong")
                    salary = " ".join(salary_tag.get_text().split()) if salary_tag else "Not specified"
                    desc_tag = card.select_one("div.nhsuk-u-margin-bottom-4")
                    description = desc_tag.get_text(strip=True) if desc_tag else ""

                    combined_text = f"{title} {description}".lower()

                    # Skip unwanted roles
                    if any(skip in combined_text for skip in SKIP_KEYWORDS):
                        continue
                    if any(re.search(pattern, combined_text) for pattern in EXCLUDE_PATTERNS):
                        continue
                    if SKIP_EXPERIENCE and any(re.search(pattern, combined_text) for pattern in EXPERIENCE_PATTERNS):
                        continue

                    all_jobs.append({
                        "title": title,
                        "link": link,
                        "trust": trust,
                        "distance": distance,
                        "posted": posted,
                        "closing": closing,
                        "salary": salary,
                        "description": description
                    })
                    seen_links.add(link)
                except Exception as e:
                    print(f"⚠️ Error parsing job card: {e}")
                    continue
            page += 1

    # Sort newest first
    all_jobs.sort(key=lambda j: parse_date_string(j["posted"]) or datetime.min, reverse=True)
    print(f"🔹 Total jobs fetched: {len(all_jobs)}")
    return all_jobs

# ================= Discord =================
def send_discord_embed(job, webhook_url):
    embed = {
        "title": f"👩‍⚕️ {job['title']}",
        "url": job['link'],
        "color": 0xE75480,
        "fields": [
            {"name": "🏥 Trust", "value": job['trust'] or "Unknown", "inline": True},
            {"name": "📍 Distance", "value": job['distance'] or "N/A", "inline": True},
            {"name": "🕒 Posted", "value": job['posted'] or "Unknown", "inline": True},
            {"name": "📅 Closing Date", "value": job['closing'] or "Unknown", "inline": True},
            {"name": "💷 Salary", "value": job['salary'] or "Not specified", "inline": False},
        ],
        "footer": {"text": "NHS Jobs Alerts"}
    }
    try:
        response = requests.post(webhook_url, json={"embeds": [embed]})
        if response.status_code == 204:
            print(f"✅ Sent: {job['title']}")
        else:
            print(f"⚠️ Discord error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error sending Discord embed: {e}")

# ================= Job Classification =================
def is_entry_level(job):
    title = job['title'].lower()
    patterns = [
        r"\bfy1\b", r"\bfy2\b", r"\bfoundation doctor\b", r"\bsho\b",
        r"\btrust doctor\b.*(st1|st2|ct1|ct2|junior)", r"\bcore trainee\b", r"\bjunior locally employed doctor\b"
    ]
    return any(re.search(pat, title) for pat in patterns)

def is_ogbyn_job(job):
    combined_text = f"{job['title']} {job['description']}".lower()
    if any(x in combined_text for x in ["obstetric", "gynaecolog", "obs & gynae", "o&g"]):
        if not is_entry_level(job):  # Don't duplicate entry jobs
            return True
    return False

# ================= Main =================
def main():
    print("🟢 job_checker.py started")
    if not WEBHOOK_OBGYN or not WEBHOOK_ENTRY:
        print("⚠️ Missing Discord webhook URL(s).")
        return

    seen = load_seen()
    new_seen = set(seen)
    jobs = fetch_jobs()

    ogbyn_jobs = []
    entry_jobs = []

    for job in jobs:
        link = job["link"]
        if link in new_seen:
            continue

        if is_entry_level(job):
            entry_jobs.append(job)
        elif is_ogbyn_job(job):
            ogbyn_jobs.append(job)

        new_seen.add(link)

    if ogbyn_jobs:
        print(f"🚨 Sending {len(ogbyn_jobs)} new O&G jobs to Discord...")
        for job in ogbyn_jobs:
            send_discord_embed(job, WEBHOOK_OBGYN)
            time.sleep(1)  # Avoid Discord rate limits
    else:
        print("ℹ️ No new O&G jobs found.")

    if entry_jobs:
        print(f"🚨 Sending {len(entry_jobs)} new entry-level jobs to Discord...")
        for job in entry_jobs:
            send_discord_embed(job, WEBHOOK_ENTRY)
            time.sleep(1)  # Avoid Discord rate limits
    else:
        print("ℹ️ No new entry-level jobs found.")

    save_seen(new_seen)
    print("🟢 Script finished")

if __name__ == "__main__":
    main()

