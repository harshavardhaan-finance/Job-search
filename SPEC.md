# Job Hunt Copilot: Build Spec

> Put this file in an empty project folder as `SPEC.md`, add your resume, and start Claude Code there.
> Claude Code: read this whole file before writing any code. Build one phase at a time (Section 12).

---

## 0. Candidate profile (source of truth for filtering and tailoring)

- **Name:** Harshavardhaan, Coimbatore, Tamil Nadu
- **Qualification:** CMA (Institute of Cost Accountants of India), June 2026. B.Com, Kumaraguru College of Liberal Arts and Science, May 2023
- **Experience:**
  - Article Assistant, C.S. Hanumantha Rao & Co. (Dec 2023 to Mar 2025): finalised accounts for individual, partnership and company clients; projected financials for bank renewals; assisted with cost audit reports, filings and job costing
  - Tax Expert, TaxBuddy (Jun 2025 to Sep 2025): ITR preparation and e-filing, client tax queries
- **Skills:** Excel, SQL, Power BI, financial reporting, financial modelling, budgeting and forecasting, variance analysis, Tally Prime. Learning Python (beginner)
- **Target roles (corporate finance and costing, behind business decisions):** FP&A analyst, business finance / commercial finance analyst, cost accountant, costing analyst, product/plant costing, management accountant, corporate financial analyst, finance business partner (junior), MIS & reporting analyst (only when analysis-heavy)
- **Exclude:** pure tax, audit, compliance, statutory/GST filing roles; client-facing practice roles; sales or "relationship manager" roles; team-lead or people-manager roles; insurance/loan advisory
- **Experience band:** 0 to 3 years
- **Pay floor:** ₹8 LPA CTC
- **Locations:** open to relocation. Priority: Bengaluru, Chennai, Hyderabad, Pune, Coimbatore, Mumbai, Delhi NCR, remote (India). Overseas roles allowed but tagged `abroad`
- **Employer preference:** large corporates, MNCs, global capability centres (GCCs), listed manufacturing companies
- **Track:** individual contributor

### Truthfulness rules (hard rules, never break)
1. Never claim Python, ML or AI proficiency. Allowed wording: "learning Python" or nothing.
2. Articleship is articleship. Never relabel it as full-time professional experience.
3. Never invent numbers, tools, titles, employers or achievements. Every line in any generated resume or cover note must trace back to `resume/master_resume.md` or `resume/achievements.md`.
4. No hype words ("dynamic", "results-driven", "passionate", "seasoned").

---

## 1. Principles

- **Legitimate sources only.** No scraping of logged-in pages on LinkedIn, Naukri, Indeed, Foundit or similar; no bots that click "Easy Apply". These sites prohibit it and ban accounts. Coverage from those sites comes through their own job-alert emails (Section 3A).
- **Polite collection:** respect robots.txt, rate-limit every source (≥2 s between requests per host), identify with a sensible User-Agent, back off on 429/403 and skip the source for the day.
- **Human submits.** The system finds, filters, scores and prepares. The candidate reviews and clicks submit.
- **Quality over volume.** Aim for 5 to 10 strong, tailored applications per day.
- **Local-first and private.** Data in local SQLite. Secrets in `.env` (never committed). `.gitignore` covers `.env`, `data/`, `output/`, `resume/`.
- **Beginner-friendly.** The owner is learning Python. Keep code readable, comment the "why", and explain each step in plain language when finishing a phase.

---

## 2. Pipeline

```
collect → normalise → dedupe → rule filter → LLM score → shortlist
       → tailor resume + cover note → review dashboard → apply (human)
       → track → follow-up reminders → weekly analytics
```

---

## 3. Sources (collectors)

Each collector is a module in `collectors/` exposing `fetch() -> list[RawJob]`. A failing collector logs the error and never stops the run.

**A. Job-alert emails (main route to LinkedIn / Naukri / Indeed / Foundit / iimjobs / Instahyre coverage)**
- The candidate creates saved-search alerts on each site, delivered to Gmail and auto-labelled `job-alerts` by a Gmail filter.
- Collector reads that label via IMAP with a Gmail app password (or Gmail API), parses each alert into title, company, location, link, and marks processed message IDs.
- One parser per sender, with a generic fallback that extracts job links + nearby text. Store unparseable emails for review instead of dropping them.

**B. Adzuna API (India endpoint)**
- Free developer key. Query each search term × priority city. Store salary fields when present.

**C. Company career pages via public ATS job-board endpoints**
- `config/target_companies.yaml`: company name, ATS type, board token/URL, tier (MNC / GCC / Indian large-cap).
- Support: Greenhouse public job-board API, Lever public postings API, SmartRecruiters public postings API, Ashby public job board, and Workday career sites (unofficial public JSON used by the career page: low rate, skip on block).
- Phase 2 task: research and **verify** a starter list of ~40 to 60 employers that hire finance/costing roles in India (GCCs with finance centres, FMCG, auto and auto-components, engineering, pharma, textiles, IT services' internal finance). Only keep entries whose endpoint actually returns jobs. The candidate edits this list.

**D. Manual add**
- Dashboard box: paste a job URL or raw JD text (for jobs found anywhere, including referrals and WhatsApp groups).

---

## 4. Data model (SQLite, `data/jobs.db`)

- `jobs`: id, source, external_id, url, title, company, location, is_remote, is_abroad, posted_date, salary_min_lpa, salary_max_lpa, salary_text, experience_text, description, dedupe_key, first_seen, last_seen
- `scores`: job_id, rule_pass, fit_score (0 to 100), role_bucket, salary_estimate_lpa, salary_basis (`stated` / `estimated`), salary_confidence, is_excluded_type, client_facing, people_mgmt, matched_skills, gaps, reasons, red_flags, model, scored_at
- `applications`: job_id, status (`new`, `shortlisted`, `tailored`, `applied`, `screening`, `interview`, `offer`, `rejected`, `skipped`, `withdrawn`), skip_reason, applied_date, resume_path, cover_note_path, contact_name, contact_link, next_follow_up, notes
- `runs`: per-run log (source, fetched, new, errors, duration)

`dedupe_key` = normalised company + normalised title + city. Same job from several sources merges into one row, keeping all URLs.

---

## 5. Filtering and scoring

**Stage 1: rules (free, fast)** using `config/search.yaml`
- Title must match an include keyword and no exclude keyword.
- Drop if required experience minimum > 4 years.
- Drop if stated salary max < 8 LPA.
- Drop jobs older than 30 days.

**Stage 2: LLM scoring (Claude API, model name configurable in `.env`)**
- Only Stage-1 survivors. Cache by description hash so nothing is scored twice. Daily cap (default 150 jobs).
- Prompt gets the candidate profile (Section 0) + JD; must return strict JSON matching the `scores` fields, with short reasons.
- Salary when not stated: estimate with confidence and basis (role, city, employer type, experience). Keep if estimate ≥ 8 LPA, or employer tier is MNC/GCC with medium/low confidence (flag `salary_unverified`).
- Auto-skip if `is_excluded_type`, `client_facing` or `people_mgmt` is true (stored with reason, visible in dashboard).
- Shortlist = fit ≥ 65 (configurable).

---

## 6. Tailoring

Inputs: `resume/master_resume.md` (true facts, full detail), `resume/achievements.md` (bullet bank with any real numbers), `config/answers.yaml` (notice period, current/expected CTC, relocation, earliest joining, links).

Per shortlisted job, on demand from the dashboard:
1. **One-page ATS resume** (.docx and .pdf): select and reorder true bullets, mirror the JD's wording where it honestly fits, simple single-column layout, no tables/graphics.
2. **Cover note** ≤ 150 words, plain and specific to the company and role.
3. **Screening answers** pre-filled from `answers.yaml`.
4. **Keyword coverage report**: JD keywords present / missing (missing ones are shown as learning gaps, never inserted).
5. **Truth check**: second pass compares every generated line against the master files; anything untraceable is flagged in red and blocked from export until the candidate edits or approves it.

Files saved to `output/<date>_<company>_<role>/`.

---

## 7. Review dashboard (Streamlit, runs locally)

- **Today:** shortlist sorted by fit, with salary (stated vs estimated badge), location, source, posted date.
- **Job detail:** JD, score reasons, gaps, red flags; buttons: Tailor, Download resume / cover note, Copy answers, Open apply link, Mark applied, Skip (with reason).
- **Pipeline:** table/kanban by status; edit status, notes, contact.
- **Follow-ups:** due today.
- **Analytics:** applications per week, response rate by source, role bucket and employer tier; top skip reasons; most common missing keywords (feeds the learning plan).
- **Settings:** edit search terms, thresholds, sources on/off.

---

## 8. Apply assistance

- Default: "Open apply link" + copy buttons. Candidate submits.
- Optional later phase: Playwright helper for **Greenhouse and Lever forms only** that fills standard fields and uploads the tailored resume, then **stops before submit**. Never used on LinkedIn, Naukri, Indeed or Foundit.

---

## 9. Follow-ups and outreach

- On `applied`: set reminders at +7 and +14 days.
- Draft a short note to a recruiter or hiring manager (LinkedIn or email) for top-fit roles. The candidate sends it personally.
- Daily digest (markdown file, optional email to self): new shortlisted jobs, follow-ups due, yesterday's stats.

---

## 10. Scheduling

- `run_daily.py` runs collect → filter → score → digest.
- Windows Task Scheduler (or cron on Mac/Linux) at 7:00 IST. README must include exact setup steps for Windows.

---

## 11. Project structure

```
job-hunt-copilot/
  SPEC.md
  README.md
  .env.example
  requirements.txt
  config/  search.yaml  target_companies.yaml  answers.yaml
  resume/  master_resume.md  achievements.md
  collectors/  email_alerts.py  adzuna.py  greenhouse.py  lever.py  smartrecruiters.py  ashby.py  workday.py  manual.py
  core/  db.py  models.py  normalise.py  dedupe.py  rules.py  scorer.py  tailor.py  truth_check.py  followups.py  digest.py
  app/  dashboard.py
  data/  (gitignored)
  output/  (gitignored)
  tests/
  run_daily.py
```

Python 3.11+, `requests`/`httpx`, `pydantic`, `sqlite3` or `sqlmodel`, `pyyaml`, `python-dotenv`, `anthropic`, `streamlit`, `python-docx`, a PDF converter, `beautifulsoup4`, `pytest`.

---

## 12. Build phases (one at a time; stop after each, show how to run and test it, explain in plain language)

| Phase | Build | Done when |
|---|---|---|
| 1 | Project skeleton, config files with examples, DB schema, manual-add, dashboard showing jobs table | I can paste a JD in the dashboard and see it stored |
| 2 | Adzuna + ATS collectors, normalise, dedupe, verified starter `target_companies.yaml` | One command fetches real jobs from ≥3 sources with no duplicates |
| 3 | Job-alert email collector (IMAP, label-based) | Alerts from at least LinkedIn and Naukri are parsed into jobs |
| 4 | Rule filter + LLM scorer with caching and daily cap | Shortlist appears in dashboard with reasons; cost per run printed |
| 5 | Tailoring + truth check + exports | Tailored resume/cover note download, untraceable lines blocked |
| 6 | Tracking, follow-ups, digest, analytics, scheduler setup | Daily run works unattended; analytics tab shows real numbers |
| 7 (optional) | Greenhouse/Lever form-fill helper that stops before submit | Form filled for a test posting, submit left to me |

Each phase: add tests for parsers and filters, update README, commit with a clear message.

---

## 13. Example `config/search.yaml`

```yaml
search_terms:
  - FP&A analyst
  - financial planning and analysis
  - cost accountant
  - costing analyst
  - business finance analyst
  - commercial finance analyst
  - management accountant
  - financial analyst
  - CMA
title_include: [fp&a, planning, cost, costing, business finance, commercial finance, management account, financial analyst, finance analyst, budget, variance, mis]
title_exclude: [tax, gst, audit, compliance, statutory, payroll, sales, relationship manager, insurance, manager - team, lead, head, director, intern]
locations: [Bengaluru, Chennai, Hyderabad, Pune, Coimbatore, Mumbai, Gurugram, Noida, Remote]
max_required_experience_years: 4
min_ctc_lpa: 8
max_job_age_days: 30
shortlist_fit_threshold: 65
daily_llm_cap: 150
```

## 14. Non-goals

- No auto-submission on any job board.
- No mass applying to low-fit roles.
- No storing passwords for job sites.
