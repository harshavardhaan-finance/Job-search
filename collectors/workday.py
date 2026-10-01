"""Workday career sites.

Workday has no official public API. Its career pages load jobs from a JSON
endpoint (/wday/cxs/...), and that is what we call, the same way the page
does. Because it is unofficial we stay extra gentle: keyword search only,
one page per keyword, details only for jobs that match and are not abroad,
and the polite client skips the site for the day if it pushes back.

In target_companies.yaml, "board" is the career site URL, e.g.
  https://acme.wd5.myworkdayjobs.com/AcmeCareers
"""
import re
from urllib.parse import urlparse

from collectors.base import fetch_all_companies
from core.models import RawJob
from core.normalise import is_abroad_location, parse_date, parse_relative_posted
from core.rules import title_matches_include

PAGE_SIZE = 20
_LOCALE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")   # e.g. "en-US" in some career URLs


def split_board_url(board_url: str) -> tuple[str, str, str]:
    """'https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers' -> (host, tenant, site)."""
    parsed = urlparse(board_url)
    parts = [p for p in parsed.path.split("/") if p and not _LOCALE.match(p)]
    if not parts:
        raise ValueError(f"Workday board URL has no site name: {board_url}")
    return parsed.netloc, parsed.netloc.split(".")[0], parts[0]


def _api_base(board_url: str) -> tuple[str, str]:
    host, tenant, site = split_board_url(board_url)
    return f"https://{host}/wday/cxs/{tenant}/{site}", f"https://{host}/{site}"


def parse_list(data: dict, include: list[str]) -> list[dict]:
    return [p for p in data.get("jobPostings", []) if title_matches_include(p.get("title", ""), include)]


def to_job(posting: dict, company: dict, public_base: str, info: dict | None = None) -> RawJob:
    info = info or {}
    location = info.get("location") or posting.get("locationsText")
    return RawJob(
        source="workday",
        external_id=f"{company['name']}:{posting['externalPath']}",
        url=info.get("externalUrl") or f"{public_base}{posting['externalPath']}",
        title=posting["title"],
        company=company["name"],
        location=location,
        posted_date=parse_date(info.get("startDate")) or parse_relative_posted(posting.get("postedOn")),
        description=info.get("jobDescription") or "",
    )


def fetch_company(company: dict, client, settings: dict) -> list[RawJob]:
    api, public_base = _api_base(company["board"])
    seen: dict[str, dict] = {}
    for keyword in settings.get("ats_keywords", []):
        payload = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": 0, "searchText": keyword}
        for posting in parse_list(client.post_json(f"{api}/jobs", payload), settings["title_include"]):
            seen.setdefault(posting["externalPath"], posting)

    jobs = []
    for posting in seen.values():
        if is_abroad_location(posting.get("locationsText")):
            jobs.append(to_job(posting, company, public_base))
            continue
        detail = client.get_json(f"{api}{posting['externalPath']}")
        jobs.append(to_job(posting, company, public_base, detail.get("jobPostingInfo")))
    return jobs


def probe(company: dict, client) -> int:
    api, _ = _api_base(company["board"])
    data = client.post_json(f"{api}/jobs", {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""})
    return int(data.get("total", 0))


def fetch(companies=None, client=None, settings=None, errors=None) -> list[RawJob]:
    return fetch_all_companies("workday", fetch_company, companies, client, settings, errors)
