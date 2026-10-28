# Jobwatch

Standalone public job-search site for my partner (an O&G doctor, also open to
care work, admin, customer support and aesthetics). GitHub Actions runs every
30 minutes, fetches jobs, merges duplicates, writes `site/jobs.json` and
`data/state.json`, and deploys to GitHub Pages.

## Layout
- `config.py` holds all settings; `build.py`, `merge.py`, `state.py`, `geo.py`
- `fetchers/`: nhs, reed, jobsac, employers, adzuna, common, flags
- `tests/`: unit tests (`python -m pytest`)
- `site/`: front end — `index.html` (markup), `style.css`, `app.js`. When
  `style.css` or `app.js` changes, bump the `?v=` number on both links in
  `index.html` so browsers drop cached copies.
- `.github/workflows/update.yml`

## Rules
- The repo is public. Never hardcode, print or commit the postcode or API keys.
  Secrets are `SEARCH_POSTCODE` and `REED_API_KEY` only; read them from the
  environment. Ask before running anything that uses them.
- Commit in small steps. Ask before pushing.
- No Discord. "New" = `first_seen` within 24h.

## Decisions
- Adzuna fetcher exists but is OFF (paid). jobs.ac.uk has no official RSS, so
  `JOBSAC_FEEDS` stays empty unless a feed URL is supplied.
- Jobs are flagged (`non-doctor-role`, `other-specialty`,
  `needs-nhs-experience`), never dropped; the site hides flagged ones by default.
- Categories: nhs, priv, res, adj, soc, gen (other work), aes (aesthetics).
- NHS Jobs also gets extra searches without the staff-group filter, because
  BPAS/MSI advertise there with pay scheme "Other".
- Reed runs every 2 hours (manual runs force it). Care/other work is searched
  within 25 miles, medical within 150.
- Pay: National Living Wage £12.71/h (update each April), full time 37.5h.
- Salary filter: by default a job shows only if its whole pay range is inside
  the slider range ("Pay fully inside salary range" toggle; off = overlap).
  Slider ends (£0, £100k) mean no lower/upper limit.

## Open work
1. Live scrapers have never been run against the real sites: check NHS
   selectors, Reed field names and the MSI careers page.
2. Atom Bank vacancies load via JavaScript; look for a JSON endpoint.
3. Add Community Integrative Care and other employers to `EMPLOYER_SOURCES`
   once vacancy page URLs are supplied.
4. Later: sync the application tracker across devices (currently localStorage).
