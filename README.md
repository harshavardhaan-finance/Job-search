# Job Hunt Copilot

A personal job-search helper. It finds, filters and prepares finance/costing jobs.
**You** review them and click submit yourself. Full design: [SPEC.md](SPEC.md).

**Status: Phase 1 done.** That covers the project skeleton, config files, the database, adding jobs by hand, and a dashboard that shows your jobs.

---

## One-time setup (Windows)

1. Install **Python 3.11 or newer** from <https://www.python.org/downloads/>.
   On the first installer screen, tick **"Add python.exe to PATH"**.
2. Open **PowerShell** and go to this project folder, for example:
   ```powershell
   cd C:\Users\<you>\Job-search
   ```
3. Create a private Python environment for this project (a "virtual environment") and switch it on:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   You'll see `(.venv)` at the start of the prompt.
   If PowerShell says *running scripts is disabled*, run this once and then try again:
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
4. Install the packages:
   ```powershell
   pip install -r requirements.txt
   ```
5. Create your private settings files (Phase 1 works without filling them in):
   ```powershell
   copy .env.example .env
   copy config\answers.example.yaml config\answers.yaml
   ```
6. Put your resume at `resume\master_resume.md`. Tailoring (Phase 5) needs it.

Whenever you open a new PowerShell window, repeat the `cd` and `.\.venv\Scripts\Activate.ps1` lines first.

## Run the dashboard

```powershell
streamlit run app/dashboard.py
```
Your browser opens at <http://localhost:8501>. To stop the dashboard, press `Ctrl+C` in PowerShell.

- **Add a job** tab: type the title and company, paste the JD (and the link if you have one), then click **Save job**.
- **Jobs** tab: lists every stored job. Pick one under *Job detail* to read its JD.

The app never opens the links you paste. It only stores them so you can click them later.
If you add the same job twice (same company, title and city), the two are merged into one row and both links are kept.

## Run the tests

```powershell
python -m pytest
```
All tests should report `passed`. They use a temporary database, so your real data is never touched.

## Where things live

| Path | What it is |
|---|---|
| `app/dashboard.py` | The Streamlit dashboard |
| `collectors/manual.py` | Turns a pasted job into a job record |
| `core/db.py` | Database tables and save/read functions (`data/jobs.db`) |
| `core/models.py` | The shape of a job record (`RawJob`) |
| `core/normalise.py`, `core/dedupe.py` | Clean-up of company, title and city text, plus the duplicate check |
| `core/config.py` | Reads `.env` and `config/*.yaml` |
| `config/search.yaml` | Search terms and filter thresholds (used from Phase 2 and Phase 4) |
| `config/target_companies.yaml` | Company career boards (filled in Phase 2) |
| `config/answers.example.yaml` | Template for your screening answers |
| `tests/` | Automated tests |

These are kept off GitHub (via `.gitignore`): `.env`, `data/`, `output/`, `resume/` and `config/answers.yaml`.
