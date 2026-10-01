"""The collection step of the pipeline: collect -> normalise -> dedupe/save.

Used by run_daily.py (command line) and by the dashboard's "Fetch jobs" tab.
Every source is run inside try/except: a failing source is logged in the
runs table and the next source still runs (SPEC.md Section 3).
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from collectors import adzuna, ashby, greenhouse, lever, smartrecruiters, workday
from core import db
from core.http import PoliteClient
from core.normalise import normalise_job

log = logging.getLogger(__name__)

# name -> fetch function. Phase 3 adds the email-alert collector here.
SOURCES = {
    "adzuna": adzuna.fetch,
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "ashby": ashby.fetch,
    "workday": workday.fetch,
}


@dataclass
class SourceResult:
    source: str
    fetched: int = 0
    new: int = 0
    merged: int = 0          # already in the database (same job seen again or on another site)
    errors: list[str] = field(default_factory=list)
    seconds: float = 0.0


def run_source(conn, name: str, fetch, client: PoliteClient) -> SourceResult:
    result = SourceResult(name)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    start = time.monotonic()
    try:
        jobs = fetch(client=client, errors=result.errors)
    except Exception as e:  # noqa: BLE001  (never let one source stop the run)
        result.errors.append(f"{type(e).__name__}: {e}")
        jobs = []
    for raw in jobs:
        try:
            _, is_new = db.save_job(conn, normalise_job(raw))
        except Exception as e:  # noqa: BLE001  (one bad record must not lose the rest)
            result.errors.append(f"could not save '{raw.title}' at {raw.company}: {e}")
            continue
        result.fetched += 1
        result.new += is_new
        result.merged += not is_new
    result.seconds = round(time.monotonic() - start, 1)
    db.log_run(conn, started_at, name, result.fetched, result.new, result.errors, result.seconds)
    return result


def run_collect(sources: list[str] | None = None, conn=None, client=None, on_progress=None) -> list[SourceResult]:
    """Run the chosen sources (default: all) and return one result per source.

    on_progress(message) is called with short status lines (the dashboard shows them live).
    """
    say = on_progress or log.info
    names = sources or list(SOURCES)
    own_conn = conn is None
    conn = conn or db.connect()
    client = client or PoliteClient()
    results = []
    try:
        for name in names:
            say(f"Fetching from {name}...")
            r = run_source(conn, name, SOURCES[name], client)
            say(f"{name}: {r.fetched} matching jobs, {r.new} new, {r.merged} already known"
                + (f", {len(r.errors)} problem(s)" if r.errors else "") + f" ({r.seconds}s)")
            results.append(r)
    finally:
        if own_conn:
            conn.close()
    return results
