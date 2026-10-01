"""The daily run (SPEC.md Section 10).

Phase 2: collect jobs from every source, clean them, merge duplicates, save.
Later phases add: rule filter + scoring (Phase 4), digest (Phase 6).

Usage:
    python run_daily.py                         # all sources
    python run_daily.py --source greenhouse     # just one (repeatable)
"""
import argparse
import logging
import sys

from core import db
from core.collect import SOURCES, run_collect


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch jobs from all sources")
    parser.add_argument("--source", action="append", choices=list(SOURCES),
                        help="only run this source (can be given more than once)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    results = run_collect(args.source, on_progress=print)

    print("\nSummary")
    for r in results:
        status = "OK" if not r.errors else f"{len(r.errors)} problem(s)"
        print(f"  {r.source:16} fetched {r.fetched:4}  new {r.new:4}  known {r.merged:4}  {status}")
        for err in r.errors[:5]:
            print(f"      - {err}")
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    dupes = db.count_duplicate_keys(conn)
    conn.close()
    working = [r.source for r in results if r.fetched > 0]
    print(f"\nJobs in database: {total}. Duplicate keys: {dupes}. Sources that returned jobs: {len(working)} {working}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
