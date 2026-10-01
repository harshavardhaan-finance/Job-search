"""Data shapes shared across the project.

RawJob is what every collector returns (SPEC.md Section 3): one job, as found,
before it is saved. Pydantic checks the types for us, so a collector that
forgets the title fails loudly instead of saving junk.
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator

# Allowed values for applications.status (SPEC.md Section 4).
APPLICATION_STATUSES = [
    "new", "shortlisted", "tailored", "applied", "screening",
    "interview", "offer", "rejected", "skipped", "withdrawn",
]


class RawJob(BaseModel):
    source: str                     # e.g. "manual", "adzuna", "greenhouse"
    external_id: str                # the source's own ID for this job
    title: str
    company: str
    url: Optional[str] = None
    location: Optional[str] = None
    is_remote: bool = False
    is_abroad: bool = False
    posted_date: Optional[date] = None
    salary_min_lpa: Optional[float] = None
    salary_max_lpa: Optional[float] = None
    salary_text: Optional[str] = None
    experience_text: Optional[str] = None
    description: str = ""

    @field_validator("title", "company")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value
