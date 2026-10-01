"""Normaliser helpers and the polite web client's rules."""
from datetime import date

import pytest

from core.http import PoliteClient, SourceBlocked
from core.models import RawJob
from core.normalise import (find_experience, html_to_text, is_abroad_location, normalise_job,
                            parse_relative_posted, parse_salary_lpa)
from core.rules import title_matches_include


@pytest.mark.parametrize("text,expected", [
    ("8-12 LPA", (8.0, 12.0)),
    ("₹8,00,000 - ₹12,00,000 per annum", (8.0, 12.0)),
    ("10 lakhs", (10.0, 10.0)),
    ("Competitive", (None, None)),
])
def test_parse_salary(text, expected):
    assert parse_salary_lpa(text) == expected


@pytest.mark.parametrize("loc,abroad", [
    ("Bengaluru, Karnataka, India", False), ("Remote", False), ("3 Locations", False), ("", False),
    ("London, United Kingdom", True), ("Remote - US", True), ("Hosur", False),
])
def test_is_abroad(loc, abroad):
    assert is_abroad_location(loc) is abroad


def test_title_include_matches_word_starts_only():
    inc = ["cost", "mis", "intern"]
    assert title_matches_include("Senior Costing Analyst", inc)
    assert not title_matches_include("Commission Specialist", ["mis"])
    assert title_matches_include("MIS Analyst", ["mis"])


def test_html_to_text_handles_escaped_html():
    assert html_to_text("&lt;p&gt;Own &lt;b&gt;budget&lt;/b&gt;&lt;/p&gt;") == "Own\nbudget"


def test_relative_dates():
    today = date(2026, 10, 1)
    assert parse_relative_posted("Posted Today", today) == today
    assert parse_relative_posted("Posted 30+ Days Ago", today) == date(2026, 9, 1)


def test_find_experience():
    assert find_experience("We need 2-4 years in FP&A") == "2-4 years"


def test_normalise_job_fills_derived_fields():
    job = RawJob(source="x", external_id="1", title="  FP&A   Analyst ", company="Acme",
                 location="London, UK", salary_text="8-12 LPA", description="<p>Need 1-3 yrs</p>")
    n = normalise_job(job)
    assert n.title == "FP&A Analyst" and n.is_abroad
    assert (n.salary_min_lpa, n.salary_max_lpa) == (8.0, 12.0)
    assert n.description == "Need 1-3 yrs" and n.experience_text == "1-3 yrs"


# ---- polite client ----------------------------------------------------------

class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload or {}, text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, responses):
        self.responses, self.headers, self.urls = responses, {}, []

    def request(self, method, url, **kw):
        self.urls.append(url)
        return self.responses.get(url, FakeResponse(payload={"ok": True}))

    def get(self, url, **kw):
        return self.request("GET", url, **kw)


def make_client(tmp_path, responses):
    sleeps = []
    clock = iter(range(0, 10_000)).__next__   # each call: 1 second later
    client = PoliteClient(block_file=tmp_path / "blocks.json", session=FakeSession(responses),
                          sleep=sleeps.append, clock=lambda: float(clock()))
    return client, sleeps


def test_waits_between_requests_to_same_host(tmp_path):
    client, sleeps = make_client(tmp_path, {"https://h.example/robots.txt": FakeResponse(404)})
    client.get_json("https://h.example/a")
    client.get_json("https://h.example/b")
    assert sleeps and all(s <= 2.0 for s in sleeps)


def test_respects_robots_txt(tmp_path):
    robots = FakeResponse(200, text="User-agent: *\nDisallow: /private")
    client, _ = make_client(tmp_path, {"https://h.example/robots.txt": robots})
    assert client.get_json("https://h.example/public") == {"ok": True}
    with pytest.raises(SourceBlocked, match="robots"):
        client.get_json("https://h.example/private/jobs")


def test_429_blocks_host_for_the_day(tmp_path):
    client, _ = make_client(tmp_path, {"https://h.example/robots.txt": FakeResponse(404),
                                       "https://h.example/jobs": FakeResponse(429)})
    with pytest.raises(SourceBlocked):
        client.get_json("https://h.example/jobs")
    # A brand-new client (e.g. a second run the same day) also skips it, without a request.
    client2, _ = make_client(tmp_path, {})
    with pytest.raises(SourceBlocked, match="earlier today"):
        client2.get_json("https://h.example/other")
    assert client2.session.urls == []


def test_unreachable_host_is_skipped_for_rest_of_run(tmp_path):
    import requests

    class DownSession(FakeSession):
        def request(self, method, url, **kw):
            self.urls.append(url)
            raise requests.ConnectionError("no route")

    client = PoliteClient(block_file=tmp_path / "b.json", session=DownSession({}), sleep=lambda s: None,
                          check_robots=False)
    with pytest.raises(SourceBlocked, match="could not be reached"):
        client.get_json("https://down.example/a")
    with pytest.raises(SourceBlocked, match="earlier in this run"):
        client.get_json("https://down.example/b")
    assert len(client.session.urls) == 1
