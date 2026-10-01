"""Manual add (SPEC.md Section 3D): a job you paste in yourself.

This does NOT visit the URL you paste. Many job sites (LinkedIn, Naukri,
Indeed...) forbid automated fetching, so the URL is only stored as a link
for you to click, and the JD text you paste is what gets saved.

fetch() exists so this module has the same shape as the other collectors,
but manual jobs come from the dashboard via build_job().
"""
import hashlib
from datetime import date

from core.models import RawJob
from core.normalise import is_remote_location


def build_job(
    *,
    title: str,
    company: str,
    description: str = "",
    url: str = "",
    location: str = "",
    is_abroad: bool = False,
    posted_date: date | None = None,
    salary_text: str = "",
    experience_text: str = "",
) -> RawJob:
    """Turn the dashboard form fields into a RawJob.

    Raises ValueError if there is neither a URL nor JD text, or if title/company is blank.
    """
    url = url.strip()
    description = description.strip()
    if not url and not description:
        raise ValueError("Paste a job URL, the JD text, or both.")

    # A stable ID for this paste: same URL (or same text) -> same ID.
    fingerprint = url or description
    external_id = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]

    location = location.strip()
    return RawJob(
        source="manual",
        external_id=external_id,
        title=title,
        company=company,
        url=url or None,
        location=location or None,
        is_remote=is_remote_location(location),
        is_abroad=is_abroad,
        posted_date=posted_date,
        salary_text=salary_text.strip() or None,
        experience_text=experience_text.strip() or None,
        description=description,
    )


def fetch() -> list[RawJob]:
    """Manual jobs are added through the dashboard, so the daily run gets nothing here."""
    return []
