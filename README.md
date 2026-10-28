# Jobwatch

A standalone job-search website. A GitHub Action runs every 30 minutes, collects jobs from several
sources, merges duplicates, remembers what it has seen, and publishes `jobs.json` plus the site on
GitHub Pages.

Sources: NHS Jobs (scraped), BMJ Careers (RSS), Reed (API), jobs.ac.uk (RSS), Spire and Ramsay
private hospitals (their careers sites' job feeds), employer careers pages (you add them in
`config.py`), and Adzuna (paid, off by default).

## One-time setup

1. **Upload the files.** In your new repo choose *Add file > Upload files* and drag in everything from
   this folder, including the `.github` folder (if the browser skips it, use *Add file > Create new
   file*, type `.github/workflows/update.yml` as the name, and paste that file's contents). Commit to `main`.
2. **Add secrets.** *Settings > Secrets and variables > Actions > New repository secret*:
   - `SEARCH_POSTCODE` - the postcode to search around (kept out of the public code)
   - `REED_API_KEY` - from reed.co.uk/developers
3. **Let the Action save history.** *Settings > Actions > General > Workflow permissions* > choose
   **Read and write permissions** > Save.
4. **Turn on Pages.** *Settings > Pages > Source* > **GitHub Actions**.
5. **Run it.** *Actions* tab > *Update jobs and deploy site* > *Run workflow*. The first run takes a
   while because it reads each new NHS advert page once (60 per run; the rest are picked up on later runs).
6. Your site address appears at the end of the *deploy* job and under *Settings > Pages*.

## Things you will probably need to tune

- **jobs.ac.uk feed address** (`JOBSAC_FEEDS` in `config.py`) is a guess. On a jobs.ac.uk search page,
  click the RSS icon, copy the link, and paste it in.
- **Employer pages** (`EMPLOYER_SOURCES` in `config.py`): add BPAS, MSI, Community Integrative Care etc.
  Check each site for a jobs feed first. Pages that load jobs with JavaScript cannot be read this way.
- **NHS Jobs page layout** can change. If the log says `nhs: ... -> 0 jobs` the scraper's selectors
  in `fetchers/nhs.py` need updating.
- **Minimum wage** is `NLW_HOURLY` in `config.py`. Update it each April.

## Reading the logs

Open *Actions*, click a run, click *build*, then *Fetch jobs*. Each source prints how many jobs it found.
A source that fails or is skipped is shown under `Not updated`; its existing jobs are left alone, never
marked stale. Logs on a public repo are public, so the code never prints your postcode or keys.

## How jobs are tracked

- `data/state.json` is the memory (committed only when something changes). `site/jobs.json` is rebuilt
  every run for the site.
- A job missing from its source is **stale** for 2 days, then **closed**, then removed after 7 days.
- Jobs are **flagged, never silently dropped** (`non-doctor-role`, `other-specialty`,
  `needs-nhs-experience`; tags `O&G`, `entry-level`). The site decides what to hide.
- Adzuna: set secrets `ENABLE_ADZUNA` = `true`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` to switch it on.
  It then runs only every 3 hours.

## Running locally

```
pip install -r requirements.txt
python -m unittest discover -s tests -t .
SEARCH_POSTCODE="..." REED_API_KEY="..." python build.py
```

GitHub switches off scheduled workflows in a public repo after about 60 days with no repo activity.
If the updates stop, press *Run workflow* once or make any small commit.
