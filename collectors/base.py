"""Shared plumbing for the company career-board collectors (SPEC.md Section 3C).

Each ATS module (greenhouse.py, lever.py, ...) only has to say how to read
ONE company's board. This file loops over the companies in
config/target_companies.yaml, and makes sure one broken company never
stops the others.
"""
import logging

from core import config
from core.http import PoliteClient
from core.models import RawJob

log = logging.getLogger(__name__)


def load_companies(ats: str | None = None) -> list[dict]:
    """Enabled entries from target_companies.yaml, optionally for one ATS type only."""
    entries = config.load_yaml("target_companies.yaml").get("companies") or []
    return [c for c in entries if c.get("enabled", True) and (ats is None or c.get("ats") == ats)]


def load_settings() -> dict:
    return config.load_yaml("search.yaml")


def fetch_all_companies(ats, fetch_company, companies=None, client=None, settings=None, errors=None):
    """Run fetch_company(company, client, settings) for every company of this ATS type."""
    companies = load_companies(ats) if companies is None else companies
    client = client or PoliteClient()
    settings = settings or load_settings()
    errors = errors if errors is not None else []
    jobs: list[RawJob] = []
    for company in companies:
        try:
            found = fetch_company(company, client, settings)
            log.info("%s (%s): %d matching jobs", company["name"], ats, len(found))
            jobs.extend(found)
        except Exception as e:  # noqa: BLE001  (one bad company must not stop the run)
            msg = f"{company.get('name')} ({ats}): {type(e).__name__}: {e}"
            log.warning(msg)
            errors.append(msg)
    return jobs
