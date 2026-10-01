"""Adzuna job-search API, India endpoint (SPEC.md Section 3B).

Needs a free key from https://developer.adzuna.com/ in .env
(ADZUNA_APP_ID and ADZUNA_APP_KEY). Searches every search term in every
priority city from config/search.yaml.

Salary note: Adzuna sometimes guesses a salary ("salary_is_predicted").
A guess is not a stated salary, so we keep it as text only and leave the
min/max numbers empty. That way the "stated salary below 8 LPA" rule never
drops a job because of Adzuna's guess.
"""
import os

from collectors.base import load_settings
from core.http import PoliteClient, SourceBlocked
from core.models import RawJob
from core.normalise import parse_date
from core.rules import title_matches_include

API = "https://api.adzuna.com/v1/api/jobs/in/search/{page}"
RESULTS_PER_PAGE = 50


class NotConfigured(Exception):
    pass


def _lpa(value) -> float | None:
    return round(float(value) / 100_000, 1) if value else None


def parse(data: dict, include: list[str]) -> list[RawJob]:
    jobs = []
    for item in data.get("results", []):
        if not title_matches_include(item.get("title", ""), include):
            continue
        smin, smax = _lpa(item.get("salary_min")), _lpa(item.get("salary_max"))
        predicted = str(item.get("salary_is_predicted", "0")) == "1"
        salary_text = None
        if smin or smax:
            salary_text = f"{'Adzuna estimate' if predicted else 'Stated'}: {smin}-{smax} LPA"
        jobs.append(RawJob(
            source="adzuna",
            external_id=str(item["id"]),
            url=item.get("redirect_url"),
            title=item.get("title", ""),
            company=(item.get("company") or {}).get("display_name") or "Unknown company",
            location=(item.get("location") or {}).get("display_name"),
            posted_date=parse_date(item.get("created")),
            salary_min_lpa=None if predicted else smin,
            salary_max_lpa=None if predicted else smax,
            salary_text=salary_text,
            description=item.get("description") or "",   # Adzuna gives a snippet, not the full JD
        ))
    return jobs


def fetch(client=None, settings=None, errors=None) -> list[RawJob]:
    app_id, app_key = os.getenv("ADZUNA_APP_ID", "").strip(), os.getenv("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        raise NotConfigured("ADZUNA_APP_ID / ADZUNA_APP_KEY are empty in .env")
    client = client or PoliteClient()
    settings = settings or load_settings()
    errors = errors if errors is not None else []
    max_pages = int(settings.get("adzuna_max_pages", 1))

    # "Remote" isn't a city Adzuna understands, so search it without a city filter.
    cities = [c for c in settings["locations"] if c.lower() != "remote"]
    wheres = cities + ([None] if len(cities) != len(settings["locations"]) else [])

    jobs: list[RawJob] = []
    for term in settings["search_terms"]:
        for where in wheres:
            for page in range(1, max_pages + 1):
                params = {
                    "app_id": app_id, "app_key": app_key, "what": term,
                    "results_per_page": RESULTS_PER_PAGE,
                    "max_days_old": settings.get("max_job_age_days", 30),
                }
                if where:
                    params["where"] = where
                try:
                    data = client.get_json(API.format(page=page), params=params)
                except SourceBlocked as e:
                    errors.append(f"adzuna: {e}")
                    return jobs          # Adzuna pushed back: stop for today
                except Exception as e:  # noqa: BLE001
                    errors.append(f"adzuna '{term}' in {where or 'anywhere'}: {type(e).__name__}: {e}")
                    break
                jobs.extend(parse(data, settings["title_include"]))
                if len(data.get("results", [])) < RESULTS_PER_PAGE:
                    break
    return jobs
