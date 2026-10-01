"""Check every company in config/target_companies.yaml (SPEC.md Section 3C).

For each entry it asks the career board how many jobs are open, then writes
the result back into the file:
    verified: true/false, open_jobs: N, checked_on: YYYY-MM-DD

Usage:
    python verify_companies.py           # check and record results
    python verify_companies.py --prune   # also delete entries that failed
"""
import argparse
import sys
from datetime import date

import yaml

from collectors import ashby, greenhouse, lever, smartrecruiters, workday
from core import config
from core.http import PoliteClient

PROBES = {
    "greenhouse": greenhouse.probe,
    "lever": lever.probe,
    "smartrecruiters": smartrecruiters.probe,
    "ashby": ashby.probe,
    "workday": workday.probe,
}
PATH = config.CONFIG_DIR / "target_companies.yaml"
HEADER = """\
# Company career boards to check (SPEC.md Section 3C). Edit freely.
#   ats:      greenhouse | lever | smartrecruiters | ashby | workday
#   board:    board token (Workday: full career-site URL)
#   tier:     MNC | GCC | Indian large-cap
#   enabled:  false = skip this company
#   verified / open_jobs / checked_on are written by: python verify_companies.py
"""


def verify(companies: list[dict], client=None, on_progress=print) -> list[dict]:
    client = client or PoliteClient()
    today = date.today().isoformat()
    for c in companies:
        try:
            n = PROBES[c["ats"]](c, client)
            c["verified"], c["open_jobs"], note = n > 0, n, f"{n} open jobs"
        except Exception as e:  # noqa: BLE001
            c["verified"], c["open_jobs"], note = False, 0, f"FAILED: {type(e).__name__}: {e}"
        c["checked_on"] = today
        on_progress(f"{'OK  ' if c['verified'] else 'FAIL'} {c['name']} ({c['ats']}): {note}")
    return companies


def save(companies: list[dict]) -> None:
    body = yaml.safe_dump({"companies": companies}, sort_keys=False, allow_unicode=True, width=120)
    PATH.write_text(HEADER + "\n" + body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prune", action="store_true", help="remove entries that failed")
    args = parser.parse_args()

    companies = config.load_yaml("target_companies.yaml").get("companies") or []
    verify(companies)
    ok = [c for c in companies if c["verified"]]
    print(f"\n{len(ok)} of {len(companies)} entries verified.")
    if args.prune:
        companies = ok
        print("Failed entries removed.")
    else:
        print("Run with --prune to remove the failed ones.")
    save(companies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
