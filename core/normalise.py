"""Small text clean-up helpers.

Phase 1 keeps these simple. Phase 2 will extend them (city aliases,
salary parsing) once real collectors feed in messy data.
"""
import re

# Common legal suffixes that make "Acme Pvt Ltd" and "Acme" look different.
_COMPANY_SUFFIXES = re.compile(
    r"\b(private|pvt|limited|ltd|llp|inc|incorporated|corp|corporation|co|company|plc|gmbh)\b\.?"
)

# Different spellings of the same city.
_CITY_ALIASES = {
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "madras": "chennai",
    "gurgaon": "gurugram",
    "new delhi": "delhi",
    "kovai": "coimbatore",
}


def clean_text(value: str | None) -> str:
    """Lowercase, keep letters/digits/&, squeeze spaces."""
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9& ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalise_company(name: str | None) -> str:
    return re.sub(r"\s+", " ", _COMPANY_SUFFIXES.sub(" ", clean_text(name))).strip()


def normalise_title(title: str | None) -> str:
    return clean_text(title)


def normalise_city(location: str | None) -> str:
    """Take the first part of 'Chennai, Tamil Nadu, India' and map aliases."""
    if not location:
        return ""
    first = clean_text(location.split(",")[0])
    return _CITY_ALIASES.get(first, first)


def is_remote_location(location: str | None) -> bool:
    text = clean_text(location)
    return "remote" in text or "work from home" in text or "wfh" in text.split()
