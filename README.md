# Job Hunt Copilot

A personal job-search helper. It finds, filters and prepares finance/costing jobs.
**You** review them and click submit yourself. Full design: [SPEC.md](SPEC.md).

**Status:** Phases 1 and 2 are built. You can add jobs by hand, fetch jobs from Adzuna and company career sites, and remove duplicates. Everything runs from a local web portal.

The portal runs **on your own computer** (http://localhost:8501). It is not on the public internet,
so your job data stays private (SPEC.md Section 1).

---

## One-time setup (Windows)

1. Install **Python 3.11 or newer** from <https://www.python.org/downloads/>.
   On the first installer screen, tick **"Add python.exe to PATH"**.
2. Double-click **`setup_windows.bat`** in the project folder.
   It creates a private Python environment (`.venv`), installs the packages, and creates
   `.env` and `config\answers.yaml` from their example files.
3. (For Adzuna) Get a free key at <https://developer.adzuna.com/> (sign up, then create an app).
   Open `.env` in Notepad and fill in `ADZUNA_APP_ID=` and `ADZUNA_APP_KEY=`.
4. Put your resume at `resume\master_resume.md`. Tailoring (Phase 5) needs it.

## Use the portal

Double-click **`start_portal.bat`**. Your browser opens the portal at <http://localhost:8501>.
Close the black window to stop it.

| Tab | What it does |
|---|---|
| **Jobs** | Every stored job. Search, filter by source, hide abroad roles, read the JD, open the links. "Seen on" lists every site the job appeared on. |
| **Fetch jobs** | Tick sources and click **Fetch now**. Progress and problems are shown live, with a log of recent runs below. |
| **Add a job** | Paste a job you found yourself (title, company, JD, link). |
| **Companies** | The company career boards that get checked. **Check all companies** confirms which boards answer and how many jobs they have open. |

**First time:** open **Companies** and click **Check all companies** (about 2 minutes).
The starter list was researched but not yet confirmed (see below).

### Same things from the command line

Open PowerShell in the project folder and run `.\.venv\Scripts\Activate.ps1` first. Then:

```powershell
python run_daily.py                       # fetch from every source
python run_daily.py --source greenhouse   # fetch from one source only
python verify_companies.py                # check every company board, record results
python verify_companies.py --prune        # ...and delete the ones that failed
streamlit run app/dashboard.py            # the portal
python -m pytest                          # run the tests
```
`fetch_jobs.bat` is a double-click shortcut for `python run_daily.py`.

## How collecting works

```
sources -> keep finance titles -> normalise -> merge duplicates -> data/jobs.db
```

- **Sources:**
  - Adzuna API: every search term × every priority city.
  - Company career boards on Greenhouse, Lever, SmartRecruiters, Ashby and Workday, read from `config/target_companies.yaml`.
- **Finance titles only:** a job is kept only if its title contains one of `title_include` from
  `config/search.yaml`, at the start of a word. So "cost" matches "Costing", but "mis" does not match "Commission".
  The rest of the Stage-1 rules (exclude words, experience, salary, age) come in Phase 4.
- **Normalise:**
  - Strips HTML from job descriptions.
  - Reads salaries such as "8-12 LPA" or "₹8,00,000".
  - Picks up "2-4 years" experience lines.
  - Tags `remote` and `abroad` (abroad = clearly outside India).
- **Duplicates:** same company + title + city counts as one job, even when spelled differently
  ("Acme Pvt Ltd, Bangalore" = "ACME, Bengaluru"). Every link is kept. The Jobs tab shows "Duplicates in database: 0".
- **Adzuna salary guesses** are kept as text only, never as a stated salary. So a guess can't trigger the "below 8 LPA" rule.

### Being polite to websites (SPEC.md Section 1)
- Reads each site's `robots.txt` and never fetches a disallowed page.
- Waits at least 2 seconds between requests to the same site.
- Sends a clear User-Agent. You can add an email address with `CONTACT_EMAIL` in `.env`.
- If a site answers 429 or 403, it is skipped for the rest of the day (recorded in `data/blocked_hosts.json`).
  If a site can't be reached at all, it is skipped for the rest of that run.
- Never logs in to anything. LinkedIn, Naukri, Indeed and Foundit are **not** scraped.
  Their jobs will arrive through job-alert emails in Phase 3.

## The starter company list

`config/target_companies.yaml` has 43 employers: 26 on Workday, 6 Greenhouse, 2 Lever, 7 SmartRecruiters and 2 Ashby.
Mostly MNCs and GCCs with finance teams in Bengaluru, Chennai, Hyderabad, Pune and Gurugram.
Each was found through a real India finance posting on that company's board (web search, 1 Oct 2026).
They are marked `verified: false` until **Check all companies** (or `verify_companies.py`) confirms that the
board answers. The two Ashby entries are start-ups and are switched off (`enabled: false`); turn them on if you want them.

To add a company, find one of its job links:

| Link looks like | Use in `target_companies.yaml` |
|---|---|
| `job-boards.greenhouse.io/acme/...` | `ats: greenhouse`, `board: acme` |
| `jobs.lever.co/acme/...` | `ats: lever`, `board: acme` |
| `jobs.smartrecruiters.com/Acme/...` | `ats: smartrecruiters`, `board: Acme` |
| `jobs.ashbyhq.com/acme/...` | `ats: ashby`, `board: acme` |
| `acme.wd5.myworkdayjobs.com/AcmeCareers/job/...` | `ats: workday`, `board: https://acme.wd5.myworkdayjobs.com/AcmeCareers` |

## Where things live

| Path | What it is |
|---|---|
| `app/dashboard.py` | The portal (Streamlit) |
| `run_daily.py` | One command to fetch from all sources |
| `verify_companies.py` | Checks the company list |
| `collectors/` | One file per source: `adzuna`, `greenhouse`, `lever`, `smartrecruiters`, `ashby`, `workday`, `manual` |
| `core/http.py` | The polite web client (robots.txt, 2-second gap, back-off) |
| `core/collect.py` | Runs the sources, cleans and saves the jobs, logs each run |
| `core/normalise.py`, `core/dedupe.py`, `core/rules.py` | Clean-up, duplicate key, title check |
| `core/db.py`, `core/models.py` | Database and the job record shape |
| `config/search.yaml` | Search terms, filters, sources on/off |
| `config/target_companies.yaml` | Company career boards |
| `tests/` | Automated tests (they use saved sample responses, never the internet) |

These are kept off GitHub (via `.gitignore`): `.env`, `data/`, `output/`, `resume/` and `config/answers.yaml`.
