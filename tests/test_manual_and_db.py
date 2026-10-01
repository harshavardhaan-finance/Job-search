"""Tests for Phase 1: manual add, dedupe key, and saving to the database.

Each test uses a throwaway database in a temp folder, never your real data/jobs.db.
"""
from datetime import date

import pytest
from pydantic import ValidationError

from collectors import manual
from core import db
from core.dedupe import make_dedupe_key

JD = "We are hiring an FP&A Analyst to own monthly variance analysis and budgeting."


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    yield c
    c.close()


# ---- manual.build_job ------------------------------------------------------

def test_build_job_from_pasted_jd():
    job = manual.build_job(title=" FP&A Analyst ", company="Acme", description=JD, location="Chennai")
    assert job.source == "manual"
    assert job.title == "FP&A Analyst"          # spaces trimmed
    assert job.url is None
    assert job.is_remote is False
    assert len(job.external_id) == 16


def test_build_job_detects_remote():
    job = manual.build_job(title="Cost Analyst", company="Acme", description=JD, location="Remote (India)")
    assert job.is_remote is True


def test_build_job_needs_url_or_text():
    with pytest.raises(ValueError, match="Paste a job URL"):
        manual.build_job(title="Cost Analyst", company="Acme")


def test_build_job_needs_title_and_company():
    with pytest.raises(ValidationError):
        manual.build_job(title="  ", company="Acme", description=JD)


def test_same_paste_gives_same_id():
    a = manual.build_job(title="X", company="Y", url="https://example.com/job/1")
    b = manual.build_job(title="X", company="Y", url="https://example.com/job/1")
    assert a.external_id == b.external_id


# ---- dedupe key --------------------------------------------------------------

def test_dedupe_key_ignores_case_suffixes_and_city_aliases():
    a = make_dedupe_key("Acme India Pvt. Ltd.", "FP&A Analyst", "Bangalore, Karnataka")
    b = make_dedupe_key("ACME India", "fp&a analyst", "Bengaluru")
    assert a == b


def test_dedupe_key_differs_by_city():
    assert make_dedupe_key("Acme", "Cost Analyst", "Pune") != make_dedupe_key("Acme", "Cost Analyst", "Chennai")


# ---- database ----------------------------------------------------------------

def test_save_and_list_job(conn):
    job = manual.build_job(title="FP&A Analyst", company="Acme", description=JD,
                           location="Chennai", posted_date=date(2026, 9, 28))
    job_id, is_new = db.save_job(conn, job)
    assert is_new
    rows = db.list_jobs(conn)
    assert len(rows) == 1
    assert rows[0]["title"] == "FP&A Analyst"
    assert rows[0]["status"] == "new"           # an applications row was created
    stored = db.get_job(conn, job_id)
    assert stored["description"] == JD
    assert stored["posted_date"] == "2026-09-28"


def test_duplicate_merges_and_keeps_both_urls(conn):
    first = manual.build_job(title="FP&A Analyst", company="Acme Pvt Ltd", location="Bangalore",
                             url="https://site-a.example/job/1", description="short")
    second = manual.build_job(title="FP&A Analyst", company="Acme", location="Bengaluru",
                              url="https://site-b.example/job/9", description=JD)
    id1, new1 = db.save_job(conn, first)
    id2, new2 = db.save_job(conn, second)
    assert (new1, new2) == (True, False)
    assert id1 == id2
    assert len(db.list_jobs(conn)) == 1
    urls = {u["url"] for u in db.get_job_urls(conn, id1)}
    assert urls == {"https://site-a.example/job/1", "https://site-b.example/job/9"}
    assert db.get_job(conn, id1)["description"] == JD   # longer JD kept


def test_schema_has_all_spec_tables(conn):
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"jobs", "scores", "applications", "runs", "job_urls"} <= names
