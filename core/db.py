"""SQLite database: table layout and the few functions that read/write jobs.

Tables follow SPEC.md Section 4. One extra table, job_urls, exists because the
spec says a job seen on several sites is merged into one row "keeping all URLs",
and a single url column can only hold one.

Run "python -m core.db" to create the database file by hand (the dashboard
also creates it automatically).
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core import config
from core.dedupe import make_dedupe_key
from core.models import RawJob

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT NOT NULL,
    external_id      TEXT,
    url              TEXT,
    title            TEXT NOT NULL,
    company          TEXT NOT NULL,
    location         TEXT,
    is_remote        INTEGER NOT NULL DEFAULT 0,
    is_abroad        INTEGER NOT NULL DEFAULT 0,
    posted_date      TEXT,
    salary_min_lpa   REAL,
    salary_max_lpa   REAL,
    salary_text      TEXT,
    experience_text  TEXT,
    description      TEXT,
    dedupe_key       TEXT NOT NULL UNIQUE,
    first_seen       TEXT NOT NULL,
    last_seen        TEXT NOT NULL
);

-- Every URL/source a job was seen at (see module docstring).
CREATE TABLE IF NOT EXISTS job_urls (
    job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source       TEXT NOT NULL,
    external_id  TEXT,
    url          TEXT,
    first_seen   TEXT NOT NULL,
    UNIQUE (job_id, source, external_id)
);

CREATE TABLE IF NOT EXISTS scores (
    job_id               INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    rule_pass            INTEGER,
    fit_score            INTEGER CHECK (fit_score BETWEEN 0 AND 100),
    role_bucket          TEXT,
    salary_estimate_lpa  REAL,
    salary_basis         TEXT CHECK (salary_basis IN ('stated', 'estimated')),
    salary_confidence    TEXT,
    is_excluded_type     INTEGER,
    client_facing        INTEGER,
    people_mgmt          INTEGER,
    matched_skills       TEXT,   -- JSON list
    gaps                 TEXT,   -- JSON list
    reasons              TEXT,   -- JSON list
    red_flags            TEXT,   -- JSON list
    model                TEXT,
    scored_at            TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    job_id           INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    status           TEXT NOT NULL DEFAULT 'new' CHECK (status IN (
                        'new', 'shortlisted', 'tailored', 'applied', 'screening',
                        'interview', 'offer', 'rejected', 'skipped', 'withdrawn')),
    skip_reason      TEXT,
    applied_date     TEXT,
    resume_path      TEXT,
    cover_note_path  TEXT,
    contact_name     TEXT,
    contact_link     TEXT,
    next_follow_up   TEXT,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    source       TEXT NOT NULL,
    fetched      INTEGER NOT NULL DEFAULT 0,
    new          INTEGER NOT NULL DEFAULT 0,
    errors       TEXT,
    duration_s   REAL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | None = None, *, check_same_thread: bool = True) -> sqlite3.Connection:
    """Open the database (creating the folder and tables if needed).

    The dashboard passes check_same_thread=False because Streamlit may reuse
    one connection from different threads.
    """
    path = Path(path) if path else config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row          # rows behave like dicts: row["title"]
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def save_job(conn: sqlite3.Connection, job: RawJob) -> tuple[int, bool]:
    """Insert a job, or merge it into an existing row with the same dedupe_key.

    Returns (job_id, is_new).
    """
    key = make_dedupe_key(job.company, job.title, job.location)
    now = _now()
    row = conn.execute("SELECT id FROM jobs WHERE dedupe_key = ?", (key,)).fetchone()

    if row:
        job_id, is_new = row["id"], False
        # Keep what we already have; only fill in fields that were empty,
        # and keep the longer description (usually the more complete one).
        conn.execute(
            """UPDATE jobs SET
                   last_seen       = ?,
                   url             = COALESCE(url, ?),
                   posted_date     = COALESCE(posted_date, ?),
                   salary_min_lpa  = COALESCE(salary_min_lpa, ?),
                   salary_max_lpa  = COALESCE(salary_max_lpa, ?),
                   salary_text     = COALESCE(salary_text, ?),
                   experience_text = COALESCE(experience_text, ?),
                   description     = CASE WHEN LENGTH(?) > LENGTH(COALESCE(description, ''))
                                          THEN ? ELSE description END
               WHERE id = ?""",
            (now, job.url, _iso(job.posted_date), job.salary_min_lpa, job.salary_max_lpa,
             job.salary_text, job.experience_text, job.description, job.description, job_id),
        )
    else:
        cur = conn.execute(
            """INSERT INTO jobs (source, external_id, url, title, company, location,
                   is_remote, is_abroad, posted_date, salary_min_lpa, salary_max_lpa,
                   salary_text, experience_text, description, dedupe_key, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job.source, job.external_id, job.url, job.title, job.company, job.location,
             int(job.is_remote), int(job.is_abroad), _iso(job.posted_date),
             job.salary_min_lpa, job.salary_max_lpa, job.salary_text, job.experience_text,
             job.description, key, now, now),
        )
        job_id, is_new = cur.lastrowid, True
        # Every new job starts in the pipeline as "new".
        conn.execute("INSERT INTO applications (job_id, status) VALUES (?, 'new')", (job_id,))

    conn.execute(
        """INSERT OR IGNORE INTO job_urls (job_id, source, external_id, url, first_seen)
           VALUES (?, ?, ?, ?, ?)""",
        (job_id, job.source, job.external_id, job.url, now),
    )
    conn.commit()
    return job_id, is_new


def list_jobs(conn: sqlite3.Connection) -> list[dict]:
    """All jobs with their application status, newest first."""
    rows = conn.execute(
        """SELECT j.id, j.title, j.company, j.location, j.is_remote, j.is_abroad,
                  j.source, j.posted_date, j.salary_text, j.experience_text,
                  j.first_seen, a.status
           FROM jobs j LEFT JOIN applications a ON a.job_id = j.id
           ORDER BY j.first_seen DESC, j.id DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_job(conn: sqlite3.Connection, job_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def get_job_urls(conn: sqlite3.Connection, job_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT source, url, first_seen FROM job_urls WHERE job_id = ? ORDER BY first_seen",
        (job_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _iso(value) -> str | None:
    return value.isoformat() if value else None


if __name__ == "__main__":
    connect().close()
    print(f"Database ready at {config.db_path()}")
