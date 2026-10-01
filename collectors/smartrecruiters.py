"""SmartRecruiters public postings API.

Docs: https://developers.smartrecruiters.com/docs/posting-api
The list endpoint has no descriptions, so we search by keyword, keep titles
that match, and only then fetch each matching job's details (one request
each). Abroad jobs are stored without a description to save requests.
"""
from collectors.base import fetch_all_companies
from core.models import RawJob
from core.normalise import parse_date
from core.rules import title_matches_include

API = "https://api.smartrecruiters.com/v1/companies/{board}/postings"
PAGE_SIZE = 100


def _location_text(loc: dict) -> str:
    if loc.get("fullLocation"):
        return loc["fullLocation"]
    parts = [loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()]
    return ", ".join(p for p in parts if p)


def _is_abroad(loc: dict) -> bool:
    country = (loc.get("country") or "").lower()
    return bool(country) and country != "in"


def parse_list(data: dict, company: dict, include: list[str]) -> list[dict]:
    """Keep only list items whose title matches. Returns the raw items."""
    return [i for i in data.get("content", []) if title_matches_include(i.get("name", ""), include)]


def parse_detail(detail: dict) -> str:
    sections = (detail.get("jobAd") or {}).get("sections") or {}
    order = ["jobDescription", "qualifications", "additionalInformation"]
    return "\n\n".join(sections[k]["text"] for k in order if (sections.get(k) or {}).get("text"))


def to_job(item: dict, company: dict, description: str = "", url: str | None = None) -> RawJob:
    loc = item.get("location") or {}
    return RawJob(
        source="smartrecruiters",
        external_id=f"{company['board']}:{item['id']}",
        url=url or f"https://jobs.smartrecruiters.com/{company['board']}/{item['id']}",
        title=item["name"],
        company=company["name"],
        location=_location_text(loc),
        is_remote=bool(loc.get("remote")),
        is_abroad=_is_abroad(loc),
        posted_date=parse_date(item.get("releasedDate")),
        experience_text=(item.get("experienceLevel") or {}).get("label"),
        description=description,
    )


def fetch_company(company: dict, client, settings: dict) -> list[RawJob]:
    url = API.format(board=company["board"])
    seen: dict[str, dict] = {}
    for keyword in settings.get("ats_keywords", []):
        data = client.get_json(url, params={"q": keyword, "limit": PAGE_SIZE, "offset": 0})
        for item in parse_list(data, company, settings["title_include"]):
            seen.setdefault(item["id"], item)

    jobs = []
    for item in seen.values():
        if _is_abroad(item.get("location") or {}):
            jobs.append(to_job(item, company))
            continue
        detail = client.get_json(f"{url}/{item['id']}")
        jobs.append(to_job(item, company, parse_detail(detail), detail.get("postingUrl")))
    return jobs


def probe(company: dict, client) -> int:
    return int(client.get_json(API.format(board=company["board"]), params={"limit": 1}).get("totalFound", 0))


def fetch(companies=None, client=None, settings=None, errors=None) -> list[RawJob]:
    return fetch_all_companies("smartrecruiters", fetch_company, companies, client, settings, errors)
