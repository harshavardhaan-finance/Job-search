"""Text clean-up helpers: turn every source's messy fields into one consistent shape.

normalise_job() is the main entry point. Every job, whichever collector it
came from, passes through it before being saved.
"""
import html
import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

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

# Any of these words in a location means the job is in India.
_INDIA_HINTS = [
    "india", "bengaluru", "bangalore", "chennai", "hyderabad", "pune", "mumbai", "delhi",
    "gurugram", "gurgaon", "noida", "coimbatore", "kolkata", "ahmedabad", "kochi", "cochin",
    "thiruvananthapuram", "trivandrum", "mysuru", "mysore", "jaipur", "chandigarh", "indore",
    "vadodara", "nagpur", "bhubaneswar", "visakhapatnam", "madurai", "hosur", "thane",
    "navi mumbai", "sriperumbudur", "tamil nadu", "karnataka", "maharashtra", "telangana",
    "haryana", "uttar pradesh", "gujarat", "kerala", "west bengal", "andhra pradesh",
]
_INDIA_RE = re.compile(r"\b(" + "|".join(re.escape(h) for h in _INDIA_HINTS) + r")\b")


def clean_text(value: str | None) -> str:
    """Lowercase, keep letters/digits/&, squeeze spaces."""
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9& ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def squeeze(value: str | None) -> str:
    """Collapse runs of whitespace; keep case and punctuation."""
    return re.sub(r"\s+", " ", value or "").strip()


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


def is_abroad_location(location: str | None) -> bool:
    """True only when the location clearly names a place outside India.

    Empty, "Remote", or vague text like "3 Locations" counts as not abroad,
    because we can't tell, and dropping a possibly-Indian job is worse.
    """
    text = clean_text(location)
    if not text or _INDIA_RE.search(text):
        return False
    leftover = re.sub(r"\b(remote|hybrid|on ?site|work from home|anywhere|locations?|multiple|\d+)\b", "", text)
    return bool(leftover.strip())


def html_to_text(value: str | None) -> str:
    """Strip HTML tags. Some APIs (Greenhouse) send HTML that is itself escaped."""
    if not value:
        return ""
    if "&lt;" in value:
        value = html.unescape(value)
    text = BeautifulSoup(value, "html.parser").get_text("\n")
    lines = [squeeze(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


# ---- salary -----------------------------------------------------------------

_NUM = r"(\d+(?:\.\d+)?)"
_LAKH_RANGE = re.compile(_NUM + r"\s*(?:-|–|to)\s*" + _NUM + r"\s*(?:lpa|lakhs?|lacs?|l\b)", re.I)
_LAKH_SINGLE = re.compile(_NUM + r"\s*(?:lpa|lakhs?|lacs?)", re.I)
_RUPEES = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]{6,})", re.I)


def parse_salary_lpa(text: str | None) -> tuple[float | None, float | None]:
    """'8-12 LPA' -> (8, 12). '₹8,00,000 - ₹12,00,000' -> (8, 12). Unknown -> (None, None)."""
    if not text:
        return None, None
    if m := _LAKH_RANGE.search(text):
        return float(m.group(1)), float(m.group(2))
    rupees = [int(n.replace(",", "")) / 100_000 for n in _RUPEES.findall(text)]
    if rupees:
        return min(rupees), max(rupees)
    if m := _LAKH_SINGLE.search(text):
        return float(m.group(1)), float(m.group(1))
    return None, None


# ---- experience -------------------------------------------------------------

_EXPERIENCE = re.compile(
    r"(\d{1,2})\s*(?:\+|(?:-|–|to)\s*(\d{1,2}))?\s*\+?\s*(?:years?|yrs?)", re.I
)


def find_experience(text: str | None) -> str | None:
    """Pull the first 'X-Y years' / 'X+ years' phrase out of a JD, as written."""
    if not text:
        return None
    m = _EXPERIENCE.search(text)
    return squeeze(m.group(0)) if m else None


# ---- dates ------------------------------------------------------------------

def parse_date(value) -> date | None:
    """Accepts ISO strings ('2026-09-30T10:00:00Z'), epoch milliseconds, or None."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000).date()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, OSError):
        return None


def parse_relative_posted(text: str | None, today: date | None = None) -> date | None:
    """Workday style: 'Posted Today', 'Posted Yesterday', 'Posted 3 Days Ago', 'Posted 30+ Days Ago'."""
    if not text:
        return None
    today = today or date.today()
    t = text.lower()
    if "today" in t:
        return today
    if "yesterday" in t:
        return today - timedelta(days=1)
    if m := re.search(r"(\d+)\+?\s*days?", t):
        return today - timedelta(days=int(m.group(1)))
    return None


# ---- the main entry point ---------------------------------------------------

def normalise_job(job):
    """Return a cleaned copy of a RawJob (see core/models.py)."""
    description = job.description or ""
    if "<" in description and ">" in description:
        description = html_to_text(description)

    salary_min, salary_max = job.salary_min_lpa, job.salary_max_lpa
    if salary_min is None and salary_max is None:
        salary_min, salary_max = parse_salary_lpa(job.salary_text)

    location = squeeze(job.location) or None
    return job.model_copy(update={
        "title": squeeze(job.title),
        "company": squeeze(job.company),
        "location": location,
        "description": description.strip(),
        "is_remote": job.is_remote or is_remote_location(location),
        "is_abroad": job.is_abroad or is_abroad_location(location),
        "salary_min_lpa": salary_min,
        "salary_max_lpa": salary_max,
        "experience_text": job.experience_text or find_experience(description),
    })
