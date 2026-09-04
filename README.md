# DMV Internship Radar

A self-updating job board for one person: internships, co-ops and part-time
research roles across DMV biotech, national labs, FFRDCs and tech employers,
filtered down to AI/ML, data science, software and computational biology.

GitHub Actions re-scrapes every six hours, commits what it found, and rebuilds
a static page on GitHub Pages. Anything that appeared since the last run is
badged **NEW**.

---

## What it watches

| Group | Where the list comes from | Roughly |
|---|---|---|
| DMV life sciences | Scraped live from the [BioPharmGuy DC-area directory](https://biopharmguy.com/links/company-by-location-dc-area.php) | ~450 companies |
| National labs, FFRDCs, universities | `src/seeds.py` | NIST, NIH, FDA, NASA Goddard, ARL, JHU APL, MITRE, Janelia, JCVI, IDA, CNA, Noblis, UMD, JHU, UMBC, Georgetown, GWU |
| Defense and government services | `src/seeds.py` | Leidos, Booz Allen, CACI, SAIC, Peraton, ManTech, GDIT, Lockheed, Northrop, BAE, Parsons, Two Six |
| Tech, finance, health systems | `src/seeds.py` | AWS, Microsoft, Google, Capital One, Fannie Mae, Freddie Mac, T. Rowe Price, Appian, Danaher, Under Armour, MedStar, Inova, Children's National, CareFirst, Aledade |
| Federal postings | USAJOBS API (optional key) | NIST, NIH, FDA, Census, CMS, NGA and every other agency in one query |

Nine job-board APIs are supported: **Greenhouse, Lever, Ashby, SmartRecruiters,
Workable, Recruitee, BambooHR, Rippling, Workday**, plus **USAJOBS**. Companies
that run a hand-written careers page instead get a plain HTML scan, and those
results are marked *Unconfirmed* on the site so you know to click through.

There is also a curated panel of programs that never appear on any job board
(NIST SURF, NIH SIP, APL college internships, NASA OSTEM, Army SEAP/CQL, HHMI
Janelia, FDA ORISE, UMD undergrad research), with their application windows.

## How it decides what to show you

Three gates, all in `src/config.py`:

1. **Location.** Washington DC, Maryland within about an hour of Ellicott City,
   Northern Virginia, or genuinely US-remote. Blacksburg, Richmond,
   Charlottesville, Delaware and the Eastern Shore are dropped, as is
   remote-but-EMEA.
2. **Role type.** Internships and co-ops, plus part-time and research-assistant
   roles. Senior, director, postdoc and "Internal Medicine" style titles are
   filtered out.
3. **Relevance.** A weighted keyword score over the title (double weight) and
   description. Bioinformatics and computational biology score highest, then
   AI/ML, then data science, then general software. Anything under
   `MIN_RELEVANCE` is dropped; anything over `STRONG_RELEVANCE` gets a
   "Strong match" badge.

Every one of those is a plain Python list you can edit. Widening the radius to
Richmond is two lines in `config.py`.

---

## Setup

**1. Create the repo**

```bash
git init
git add -A
git commit -m "Initial commit"
gh repo create dmv-internship-radar --private --source=. --push
# or create it on github.com and: git remote add origin <url> && git push -u origin main
```

**2. Let the workflow write to the repo**

Settings → Actions → General → Workflow permissions → **Read and write permissions**.
The scraper commits `data/jobs.json` (that file is what remembers when each
posting first appeared) and `docs/index.html` on every run.

**3. Turn on Pages**

Settings → Pages → Source: **Deploy from a branch** → Branch `main`, folder
`/docs`. Your page lands at `https://<you>.github.io/dmv-internship-radar/`.

**4. Run it once**

Actions → *Update internship radar* → **Run workflow**. The first run does full
board discovery across ~500 companies and takes roughly 15-25 minutes. Later
runs reuse the cached board map and take 3-6 minutes.

**5. Optional: add federal postings**

Get a free key at <https://developer.usajobs.gov/apirequest/>, then add two
repository secrets (Settings → Secrets and variables → Actions):

- `USAJOBS_API_KEY` - the key they email you
- `USAJOBS_EMAIL` - the address you registered with

Without these the federal source is skipped silently. It is worth doing: NIST,
NIH and FDA are all a short drive away and all post through USAJOBS.

---

## Running it locally

```bash
pip install -r requirements.txt

python run.py                    # discover (if stale), scrape, rebuild the page
python run.py --limit 30 -v      # quick smoke test against 30 companies
python run.py --skip-discovery   # scrape using the cached board map only
python run.py --force-discovery  # re-check every company's board (slow)
python run.py --rebuild-site     # regenerate docs/index.html, no network
```

Then open `docs/index.html`.

Tests run without network:

```bash
python tests/test_match.py
python tests/test_pipeline.py
python tests/test_discovery.py
```

---

## Layout

```
run.py                  orchestrator / CLI
src/config.py           every tunable: cities, role patterns, keyword weights
src/directory.py        scrapes the BioPharmGuy directory
src/seeds.py            non-biotech employers + the curated programs panel
src/discover.py         finds and validates each company's job board
src/ats/                one module per job-board API
src/match.py            location / role / relevance gates
src/store.py            data/jobs.json, first-seen tracking, NEW detection
src/site.py             renders docs/index.html
data/companies.json     the watch list, rebuilt each run
data/ats.json           company -> job board map (cached 7 days)
data/jobs.json          current postings + when each was first seen
data/companies_snapshot.json  fallback list if the directory scrape fails
docs/index.html         the site
```

## Honest limitations

- **Discovery is best-effort.** A company whose careers page is a JavaScript
  app with no ATS fingerprint will not be found. Add it by hand to
  `data/ats.json` if you spot one worth having.
- **iCIMS and Taleo are not supported.** Neither exposes a usable public JSON
  API. Some large employers use them; their roles will only show up through
  the low-confidence HTML scan or USAJOBS.
- **Workday boards are searched, not enumerated.** The connector queries for
  intern/co-op/student/summer rather than pulling every posting, so a
  strangely-titled internship at a Workday employer could be missed.
- **The HTML fallback is noisy on purpose.** Those rows are labelled
  *Unconfirmed - check the page*. Trust the ATS-sourced rows.
- **Keyword relevance is a heuristic.** If something good is being filtered
  out, lower `MIN_RELEVANCE` or add the keyword to `RELEVANCE_KEYWORDS`.
- Always apply through the employer's own site. Nothing here submits anything
  on your behalf.
