"""Ashby public job-board API.

Docs: https://developers.ashbyhq.com/docs/public-job-posting-api
One request returns every job, with descriptions and (if published) pay.
"""
from collectors.base import fetch_all_companies
from core.models import RawJob
from core.normalise import parse_date
from core.rules import title_matches_include

API = "https://api.ashbyhq.com/posting-api/job-board/{board}"


def parse(data: dict, company: dict, include: list[str]) -> list[RawJob]:
    jobs = []
    for item in data.get("jobs", []):
        if not title_matches_include(item.get("title", ""), include):
            continue
        address = ((item.get("address") or {}).get("postalAddress") or {})
        country = address.get("addressCountry") or ""
        jobs.append(RawJob(
            source="ashby",
            external_id=f"{company['board']}:{item.get('id') or item.get('jobUrl')}",
            url=item.get("jobUrl") or item.get("applyUrl"),
            title=item["title"],
            company=company["name"],
            location=item.get("location"),
            is_remote=bool(item.get("isRemote")),
            is_abroad=bool(country) and "india" not in country.lower(),
            posted_date=parse_date(item.get("publishedAt")),
            salary_text=(item.get("compensation") or {}).get("compensationTierSummary"),
            description=item.get("descriptionPlain") or item.get("descriptionHtml") or "",
        ))
    return jobs


def fetch_company(company: dict, client, settings: dict) -> list[RawJob]:
    data = client.get_json(API.format(board=company["board"]), params={"includeCompensation": "true"})
    return parse(data, company, settings["title_include"])


def probe(company: dict, client) -> int:
    return len(client.get_json(API.format(board=company["board"])).get("jobs", []))


def fetch(companies=None, client=None, settings=None, errors=None) -> list[RawJob]:
    return fetch_all_companies("ashby", fetch_company, companies, client, settings, errors)
