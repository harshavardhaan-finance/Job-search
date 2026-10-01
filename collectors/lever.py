"""Lever public postings API.

Docs: https://github.com/lever/postings-api
One request returns every posting, with plain-text descriptions.
Set "region: eu" in target_companies.yaml for companies hosted on Lever's EU servers.
"""
from collectors.base import fetch_all_companies
from core.models import RawJob
from core.normalise import parse_date
from core.rules import title_matches_include


def _api(company: dict) -> str:
    host = "api.eu.lever.co" if company.get("region") == "eu" else "api.lever.co"
    return f"https://{host}/v0/postings/{company['board']}"


def _salary_text(item: dict) -> str | None:
    rng = item.get("salaryRange") or {}
    if not rng.get("min"):
        return None
    return f"{rng.get('currency', '')} {rng['min']:,} - {rng.get('max', rng['min']):,} {rng.get('interval', '')}".strip()


def parse(data: list, company: dict, include: list[str]) -> list[RawJob]:
    jobs = []
    for item in data:
        if not title_matches_include(item.get("text", ""), include):
            continue
        cats = item.get("categories") or {}
        country = (item.get("country") or "").upper()
        jobs.append(RawJob(
            source="lever",
            external_id=f"{company['board']}:{item['id']}",
            url=item.get("hostedUrl"),
            title=item["text"],
            company=company["name"],
            location=cats.get("location"),
            is_remote=(item.get("workplaceType") == "remote"),
            is_abroad=bool(country) and country != "IN",
            posted_date=parse_date(item.get("createdAt")),
            salary_text=_salary_text(item),
            description=item.get("descriptionPlain") or item.get("description") or "",
        ))
    return jobs


def fetch_company(company: dict, client, settings: dict) -> list[RawJob]:
    data = client.get_json(_api(company), params={"mode": "json"})
    return parse(data, company, settings["title_include"])


def probe(company: dict, client) -> int:
    return len(client.get_json(_api(company), params={"mode": "json"}))


def fetch(companies=None, client=None, settings=None, errors=None) -> list[RawJob]:
    return fetch_all_companies("lever", fetch_company, companies, client, settings, errors)
