"""All settings in one place. Edit this file to change what the site fetches."""
import os
import re

# --- Pay rules ---------------------------------------------------------------
NLW_HOURLY = 12.71        # National Living Wage (age 21+) from April 2026. Update each April.
FULL_TIME_HOURS = 37.5

# --- Search area (the postcode comes from a GitHub secret, never from the code) ---
SEARCH_POSTCODE = os.getenv("SEARCH_POSTCODE", "").strip()
RADIUS_MILES = 150

# --- Behaviour ---------------------------------------------------------------
USER_AGENT = "jobwatch/1.0 (personal job-search tool)"
REQUEST_DELAY = 0.6       # seconds between requests, to be polite to the sites
STALE_DAYS = 2            # missing from its source for this long -> "closed"
DROP_DAYS = 7             # missing this long -> removed from the site
MAX_DETAIL_PER_RUN = 60   # NHS advert pages fetched per run (hours / contract type)
NHS_MAX_PAGES = 15

# --- NHS Jobs ----------------------------------------------------------------
NHS_KEYWORDS = [
    "obstetrics", "gynaecology", "obs & gynae", "o&g", "pregnancy",
    "trust grade", "trust doctor", "FY1", "FY2", "SHO",
    "foundation doctor", "core trainee", "obstetrics and gynaecology", "women's health",
    "clinical fellow", "junior clinical fellow", "senior clinical fellow",
    "resident doctor", "LAS", "MTI", "locally employed doctor",
]
NHS_STAFF_GROUP = "MEDICAL_AND_DENTAL"
NHS_PAY_BANDS = ["SPECIALTY_DOCTOR", "FOUNDATION_DOCTOR", "SPECIALTY_REGISTRAR",
                 "DOCTOR_OTHER", "SPECIALIST"]
# Extra searches WITHOUT the staff-group / pay-band filters. Independent providers such as BPAS and
# MSI advertise on NHS Jobs with pay scheme "Other", so the filters above could hide their roles.
# Nurses/midwives that come back are labelled "non-doctor-role" and hidden on the site by default.
NHS_EXTRA_KEYWORDS = ["BPAS", "MSI Reproductive Choices", "abortion", "termination of pregnancy",
                      "sexual and reproductive health", "contraception"]
# NHS Jobs employers that should show under "Private & independent" instead of "NHS clinical"
PRIVATE_PROVIDERS = ["bpas", "british pregnancy advisory", "msi reproductive", "marie stopes"]

# --- Reed (needs REED_API_KEY). (search words, category) ---------------------
# categories: nhs, priv (private/independent), res (research), adj (medical-adjacent), soc (social care), gen (other work), aes (aesthetics)
REED_QUERIES = [
    # medical and medical-adjacent
    ("obstetrics gynaecology doctor", "priv"),
    ("gynaecology specialist doctor", "priv"),
    ("abortion care doctor", "priv"),
    ("sexual and reproductive health doctor", "priv"),
    ("women's health doctor", "priv"),
    ("clinical research physician", "res"),
    ("medical affairs women's health", "adj"),
    ("medical advisor pharmaceutical", "adj"),
    ("clinical education obstetrics", "adj"),
    # aesthetics / cosmetic medicine
    ("aesthetic doctor", "aes"),
    ("aesthetic practitioner", "aes"),
    ("cosmetic doctor", "aes"),
    ("cosmetic injector", "aes"),
    ("aesthetic medicine", "aes"),
    ("cosmetic surgery", "aes"),
    # care and support work
    ("social care worker", "soc"),
    ("support worker", "soc"),
    ("senior support worker", "soc"),
    ("care assistant", "soc"),
    ("care worker", "soc"),
    ("healthcare assistant", "soc"),
    # any other decent-paying work (gen = "Other work")
    ("customer support agent", "gen"),
    ("customer service advisor", "gen"),
    ("administrator", "gen"),
    ("receptionist", "gen"),
    ("medical receptionist", "gen"),
    ("office assistant", "gen"),
    ("data entry", "gen"),
]
# Everyday jobs are searched closer to home than medical roles
LOCAL_RADIUS_MILES = 25
LOCAL_CATEGORIES = ("soc", "gen")
# Reed is only queried every N hours (and on manual runs) to be gentle on its API
REED_EVERY_HOURS = 2
REED_FULL_TIME_ONLY = True
REED_MAX_RESULTS = 300    # per query

# --- jobs.ac.uk RSS feeds: (feed URL, category) -------------------------------
# Leave empty to skip. To fill in: open https://www.jobs.ac.uk/feeds, find the subject you want
# (e.g. medicine / health), right-click its "RSS Feed" link, copy the link address, and add it:
# JOBSAC_FEEDS = [("PASTE-THE-LINK-HERE", "res")]
JOBSAC_FEEDS = []
# Subject feeds are broad, so only jobs whose title/summary mention one of these words are kept.
JOBSAC_KEYWORDS = (r"obstetric|gynaecolog|women'?s health|maternal|maternity|reproductive|fertility|"
                   r"pregnan|midwi|abortion|contracepti|clinical research|clinical trial")

# --- Employer careers pages --------------------------------------------------
# BPAS has no vacancies page of its own (it advertises on NHS Jobs), so it is covered above.
# MSI has its own recruitment site as well as NHS Jobs. Duplicates are merged automatically.
# NOT YET CHECKED against a live vacancy list (when I looked it said "no vacancies"): if the log
# shows "0 links" while jobs are listed, link_contains / title_regex need adjusting.
EMPLOYER_SOURCES = [
    {"name": "MSI Reproductive Choices",
     "url": "https://careers.msichoices.org/Search.aspx?l=uk",
     "category": "priv",
     "link_contains": "VacancyInformation",
     "title_regex": r"doctor|surgeon|practitioner|clinician|medical|gynae|obstet|abortion|contracepti|sexual|reproductive"},
]

# --- Adzuna (PAID, switched off unless ENABLE_ADZUNA=true plus keys) ----------
ADZUNA_EVERY_HOURS = 3

# --- Flags: nothing is dropped, jobs are just labelled so the site can hide them
NON_DOCTOR_WORDS = ["midwife", "midwives", "midwifery", "nurse", "nursing", "administrative",
                    "administrator", "admin", "assistant", "ward clerk", "receptionist",
                    "training programme director"]
OTHER_SPECIALTY_PATTERNS = [
    r"\bhistopathology\b", r"\bcardiopulmonary\b", r"\btransplantation\b", r"\bcardiology\b",
    r"\boncology\b", r"\banaesth\w*\b", r"\bintensive care\b", r"\bcritical care\b", r"\bdental\b",
    r"\bemergency medicine\b", r"\bophthalmology\b", r"\bpaediatrics\b", r"\bradiology\b",
    r"\bpathology\b", r"\bpsychiatry\b", r"\bgeriatrics\b", r"\bneurology\b", r"\burology\b",
    r"\borthopaedics\b", r"\bent\b", r"\bdermatology\b", r"\bgim\b", r"\bvascular\b", r"\bgp\b",
    r"\bnephrology\b", r"\bhaematology\b", r"\brheumatology\b", r"\bgastroenterology\b",
    r"\bspinal\b", r"\bplastic surgery\b", r"\bcolorectal\b", r"\brespiratory\b", r"\bthoracic\b",
    r"\brenal\b", r"\bcardiothoracic\b", r"\bchildren\b", r"\bneuro\b",
]
EXPERIENCE_PATTERNS = [
    r"2\s+years?\s+nhs\s+experience", r"two\s+years?\s+nhs\s+experience",
    r"previous\s+nhs\s+experience\s+(essential|required)",
]
OG_PATTERN = re.compile(r"obstetric|gynaecolog|obs ?(&|and) ?gynae|\bo&g\b|women'?s health|maternity", re.I)
ENTRY_PATTERN = re.compile(r"\bfy[12]\b|foundation doctor|\bsho\b|core trainee|trust grade|junior (clinical|locally)", re.I)
