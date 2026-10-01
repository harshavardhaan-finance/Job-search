"""The collect step end to end: several sources, cross-source duplicates, a failing source."""
from core import collect, db
from core.models import RawJob


def _job(source, ext, company, title, location, url):
    return RawJob(source=source, external_id=ext, company=company, title=title, location=location, url=url,
                  description=f"JD from {source}")


def test_run_collect_merges_duplicates_and_survives_failures(tmp_path, monkeypatch):
    def src_a(client=None, errors=None):
        return [_job("a", "1", "Acme India Pvt Ltd", "FP&A Analyst", "Bangalore", "https://a/1"),
                _job("a", "2", "Beta", "Cost Accountant", "Chennai", "https://a/2")]

    def src_b(client=None, errors=None):
        # Same Acme job as source a, spelled differently -> must merge, not duplicate.
        return [_job("b", "9", "ACME India", "FP&A analyst", "Bengaluru, Karnataka", "https://b/9")]

    def src_broken(client=None, errors=None):
        raise ConnectionError("site down")

    monkeypatch.setattr(collect, "SOURCES", {"a": src_a, "broken": src_broken, "b": src_b})
    conn = db.connect(tmp_path / "t.db")
    results = {r.source: r for r in collect.run_collect(conn=conn, client=object())}

    assert results["a"].new == 2
    assert results["b"].new == 0 and results["b"].merged == 1
    assert results["broken"].errors and "site down" in results["broken"].errors[0]
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2
    assert db.count_duplicate_keys(conn) == 0
    acme = [j for j in db.list_jobs(conn) if j["company"].startswith("Acme")][0]
    assert set(acme["seen_on"].split(",")) == {"a", "b"}
    assert len(db.list_runs(conn)) == 3          # every source logged, including the broken one
