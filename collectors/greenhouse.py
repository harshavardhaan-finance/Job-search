"""Greenhouse public job-board API.

Docs: https://developers.greenhouse.io/job-board.html
One request returns every open job on a company's board, with descriptions.
"""
from collectors.base import fetch_all_companies
from core.models import RawJob
from core.normalise import parse_date
from core.rules import title_matches_include

API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def parse(data: dict, company: dict, include: list[str]) -> list[RawJob]:
    jobs = []
    for item in data.get("jobs", []):
        if not title_matches_include(item.get("title", ""), include):
            continue
        jobs.append(RawJob(
            source="greenhouse",
            external_id=f"{company['board']}:{item['id']}",
            url=item.get("absolute_url"),
            title=item["title"],
            company=company["name"],
            location=(item.get("location") or {}).get("name"),
            posted_date=parse_date(item.get("first_published") or item.get("updated_at")),
            description=item.get("content") or "",
        ))
    return jobs


def fetch_company(company: dict, client, settings: dict) -> list[RawJob]:
    data = client.get_json(API.format(board=company["board"]), params={"content": "true"})
    return parse(data, company, settings["title_include"])


def probe(company: dict, client) -> int:
    """How many open jobs the board has (used to verify the company list)."""
    return len(client.get_json(API.format(board=company["board"])).get("jobs", []))


def fetch(companies=None, client=None, settings=None, errors=None) -> list[RawJob]:
    return fetch_all_companies("greenhouse", fetch_company, companies, client, settings, errors)
