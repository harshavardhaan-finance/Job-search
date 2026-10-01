"""Collector parsers, using small samples shaped like each API's real responses."""
import pytest

from collectors import adzuna, ashby, greenhouse, lever, smartrecruiters, workday
from tests.fakes import SETTINGS, FakeClient

INC = SETTINGS["title_include"]


def test_greenhouse_keeps_matching_titles_only():
    data = {"jobs": [
        {"id": 11, "title": "FP&A Analyst", "absolute_url": "https://x/11",
         "location": {"name": "Bengaluru, India"}, "first_published": "2026-09-25T10:00:00Z",
         "content": "&lt;p&gt;Own the &lt;b&gt;budget&lt;/b&gt;&lt;/p&gt;"},
        {"id": 12, "title": "Software Engineer", "absolute_url": "https://x/12", "location": {"name": "Pune"}},
    ]}
    jobs = greenhouse.parse(data, {"name": "Acme", "board": "acme"}, INC)
    assert [j.title for j in jobs] == ["FP&A Analyst"]
    j = jobs[0]
    assert j.external_id == "acme:11" and j.company == "Acme" and str(j.posted_date) == "2026-09-25"


def test_lever_tags_abroad_by_country_and_reads_salary():
    data = [
        {"id": "a1", "text": "Cost Accountant", "hostedUrl": "https://jobs.lever.co/acme/a1",
         "categories": {"location": "Chennai"}, "country": "IN", "createdAt": 1758800000000,
         "descriptionPlain": "Plant costing", "salaryRange": {"min": 800000, "max": 1200000,
                                                             "currency": "INR", "interval": "per-year-salary"}},
        {"id": "a2", "text": "Financial Analyst", "hostedUrl": "https://jobs.lever.co/acme/a2",
         "categories": {"location": "London"}, "country": "GB", "workplaceType": "remote"},
    ]
    jobs = lever.parse(data, {"name": "Acme", "board": "acme"}, INC)
    assert [j.is_abroad for j in jobs] == [False, True]
    assert jobs[1].is_remote
    assert "800,000" in jobs[0].salary_text


def test_ashby_parse():
    data = {"jobs": [{"id": "z9", "title": "MIS Analyst", "location": "Bengaluru", "isRemote": False,
                      "jobUrl": "https://jobs.ashbyhq.com/acme/z9", "publishedAt": "2026-09-20T00:00:00Z",
                      "descriptionPlain": "Monthly MIS", "address": {"postalAddress": {"addressCountry": "India"}},
                      "compensation": {"compensationTierSummary": "₹10L – ₹14L"}}]}
    jobs = ashby.parse(data, {"name": "Acme", "board": "acme"}, INC)
    assert len(jobs) == 1 and not jobs[0].is_abroad and jobs[0].salary_text == "₹10L – ₹14L"


def test_smartrecruiters_fetches_details_only_for_india_jobs():
    base = "api.smartrecruiters.com/v1/companies/Acme/postings"
    client = FakeClient({
        base: {"content": [
            {"id": "1", "name": "Financial Analyst", "releasedDate": "2026-09-28T00:00:00Z",
             "location": {"city": "Hyderabad", "country": "in"}},
            {"id": "2", "name": "Financial Analyst", "location": {"city": "Austin", "country": "us"}},
            {"id": "3", "name": "Java Developer", "location": {"city": "Pune", "country": "in"}},
        ]},
        base + "/1": {"postingUrl": "https://jobs.smartrecruiters.com/Acme/1",
                      "jobAd": {"sections": {"jobDescription": {"text": "<p>FP&amp;A work</p>"}}}},
    })
    jobs = smartrecruiters.fetch_company({"name": "Acme", "board": "Acme"}, client, SETTINGS)
    assert {j.external_id for j in jobs} == {"Acme:1", "Acme:2"}
    detail_calls = [u for _, u, _ in client.calls if u.endswith("/1") or u.endswith("/2")]
    assert detail_calls == ["https://" + base + "/1"]      # no detail request for the US job


def test_workday_url_split_handles_locale():
    assert workday.split_board_url("https://acme.wd5.myworkdayjobs.com/en-US/AcmeCareers") == \
        ("acme.wd5.myworkdayjobs.com", "acme", "AcmeCareers")


def test_workday_fetch_company():
    api = "acme.wd5.myworkdayjobs.com/wday/cxs/acme/Ext"
    client = FakeClient({
        api + "/jobs": {"total": 2, "jobPostings": [
            {"title": "Costing Analyst", "externalPath": "/job/Chennai/Costing-Analyst_R1",
             "locationsText": "Chennai, Tamil Nadu, India", "postedOn": "Posted 2 Days Ago"},
            {"title": "Costing Analyst", "externalPath": "/job/Ohio/Costing-Analyst_R2",
             "locationsText": "Cleveland, Ohio, United States", "postedOn": "Posted Today"},
        ]},
        api + "/job/Chennai/Costing-Analyst_R1": {"jobPostingInfo": {
            "jobDescription": "<p>Product costing</p>", "location": "Chennai, Tamil Nadu, India",
            "startDate": "2026-09-29", "externalUrl": "https://acme.wd5.myworkdayjobs.com/Ext/job/R1"}},
    })
    jobs = workday.fetch_company({"name": "Acme", "board": "https://acme.wd5.myworkdayjobs.com/Ext"}, client, SETTINGS)
    by_path = {j.external_id: j for j in jobs}
    india = by_path["Acme:/job/Chennai/Costing-Analyst_R1"]
    assert india.description == "<p>Product costing</p>" and str(india.posted_date) == "2026-09-29"
    assert by_path["Acme:/job/Ohio/Costing-Analyst_R2"].description == ""


def test_adzuna_predicted_salary_is_not_stored_as_stated():
    data = {"results": [
        {"id": 1, "title": "FP&A Analyst", "company": {"display_name": "Acme"},
         "location": {"display_name": "Chennai, Tamil Nadu"}, "created": "2026-09-29T08:00:00Z",
         "salary_min": 600000, "salary_max": 900000, "salary_is_predicted": "1", "redirect_url": "https://a/1"},
        {"id": 2, "title": "Cost Accountant", "company": {"display_name": "Beta"},
         "salary_min": 900000, "salary_max": 1200000, "salary_is_predicted": "0"},
        {"id": 3, "title": "Sales Executive", "company": {"display_name": "Gamma"}},
    ]}
    jobs = adzuna.parse(data, INC)
    assert [j.title for j in jobs] == ["FP&A Analyst", "Cost Accountant"]
    assert jobs[0].salary_max_lpa is None and "estimate" in jobs[0].salary_text
    assert (jobs[1].salary_min_lpa, jobs[1].salary_max_lpa) == (9.0, 12.0)


def test_adzuna_without_keys_says_so(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    with pytest.raises(adzuna.NotConfigured):
        adzuna.fetch(client=FakeClient({}), settings=SETTINGS)


def test_one_broken_company_does_not_stop_the_others():
    client = FakeClient({
        "boards/broken/jobs": RuntimeError("boom"),
        "boards/good/jobs": {"jobs": [{"id": 1, "title": "FP&A Analyst", "absolute_url": "u"}]},
    })
    errors = []
    jobs = greenhouse.fetch(companies=[{"name": "Broken", "board": "broken"}, {"name": "Good", "board": "good"}],
                            client=client, settings=SETTINGS, errors=errors)
    assert len(jobs) == 1 and len(errors) == 1 and "Broken" in errors[0]
