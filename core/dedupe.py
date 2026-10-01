"""Builds the dedupe_key (SPEC.md Section 4).

dedupe_key = normalised company + normalised title + city.
Two postings with the same key are treated as the same job.
"""
from core.normalise import normalise_city, normalise_company, normalise_title


def make_dedupe_key(company: str, title: str, location: str | None) -> str:
    return "|".join([normalise_company(company), normalise_title(title), normalise_city(location)])
