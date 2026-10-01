"""Job Hunt Copilot portal (SPEC.md Section 7). Runs on your own computer.

Start it from the project folder with:
    streamlit run app/dashboard.py
(or double-click start_portal.bat on Windows)
"""
import sys
from pathlib import Path

# Streamlit runs this file directly, so Python would not find the "core" and
# "collectors" folders. Adding the project root to the search path fixes that.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import verify_companies  # noqa: E402
from collectors import manual  # noqa: E402
from core import config, db  # noqa: E402
from core.collect import SOURCES, run_collect  # noqa: E402
from core.normalise import normalise_job  # noqa: E402

st.set_page_config(page_title="Job Hunt Copilot", layout="wide")
st.title("Job Hunt Copilot")


@st.cache_resource
def get_conn():
    # One shared connection for the whole app, opened once.
    return db.connect(check_same_thread=False)


conn = get_conn()
tab_jobs, tab_fetch, tab_add, tab_companies = st.tabs(["Jobs", "Fetch jobs", "Add a job", "Companies"])

# The tabs that change data run first (even though they are shown later) so
# anything saved in this run already appears in the Jobs table below.

# ---------------------------------------------------------------- Fetch jobs
with tab_fetch:
    st.write(
        "Collect jobs from job APIs and company career sites. The app waits 2 seconds between "
        "requests to each site and follows each site's robots.txt, so a full run takes a few minutes."
    )
    defaults = config.load_yaml("search.yaml").get("sources", {})
    cols = st.columns(len(SOURCES))
    chosen = [name for col, name in zip(cols, SOURCES) if col.checkbox(name, value=defaults.get(name, True))]
    if st.button("Fetch now", type="primary", disabled=not chosen):
        with st.status("Fetching jobs...", expanded=True) as status:
            results = run_collect(chosen, conn=conn, on_progress=st.write)
            new = sum(r.new for r in results)
            status.update(label=f"Done: {new} new job(s). See the Jobs tab.", state="complete")
        for r in results:
            for err in r.errors[:10]:
                st.warning(f"{r.source}: {err}")

    st.subheader("Recent runs")
    runs = db.list_runs(conn, limit=30)
    if runs:
        st.dataframe(
            [{"When (UTC)": r["started_at"].replace("T", " ")[:16], "Source": r["source"],
              "Matching jobs": r["fetched"], "New": r["new"], "Seconds": r["duration_s"],
              "Problems": (r["errors"] or "").replace("\n", " | ")} for r in runs],
            width="stretch", hide_index=True,
        )
    else:
        st.caption("No runs yet.")

# ---------------------------------------------------------------- Add a job
with tab_add:
    st.write(
        "Paste a job you found anywhere (job site, referral, WhatsApp group). "
        "The link is only saved, never opened by the app: paste the JD text too."
    )
    with st.form("manual_add", clear_on_submit=True):
        col1, col2 = st.columns(2)
        title = col1.text_input("Job title *")
        company = col2.text_input("Company *")
        url = st.text_input("Job URL (optional)")
        description = st.text_area("Job description (paste the full JD)", height=250)
        col3, col4, col5 = st.columns(3)
        location = col3.text_input("Location", placeholder="e.g. Chennai, or Remote")
        salary_text = col4.text_input("Salary (as written)", placeholder="e.g. 8-12 LPA")
        experience_text = col5.text_input("Experience (as written)", placeholder="e.g. 0-3 years")
        col6, col7 = st.columns(2)
        posted_date = col6.date_input("Posted date (if known)", value=None)
        is_abroad = col7.checkbox("Role is outside India")
        submitted = st.form_submit_button("Save job")

    if submitted:
        try:
            job = manual.build_job(
                title=title, company=company, description=description, url=url,
                location=location, is_abroad=is_abroad, posted_date=posted_date,
                salary_text=salary_text, experience_text=experience_text,
            )
        except ValidationError as e:
            fields = ", ".join(str(err["loc"][0]) for err in e.errors())
            st.error(f"Please fill in: {fields}")
        except ValueError as e:
            st.error(str(e))
        else:
            job_id, is_new = db.save_job(conn, normalise_job(job))
            if is_new:
                st.success(f"Saved as job #{job_id}: {job.title} at {job.company}. See the Jobs tab.")
            else:
                st.info(f"Already had this job (#{job_id}); merged the new details into it.")

# ---------------------------------------------------------------- Companies
with tab_companies:
    st.write(
        "Company career boards checked by the **Fetch jobs** tab. Edit `config/target_companies.yaml` "
        "to add, remove or turn off companies. **Check all companies** asks each board how many jobs "
        "are open and records the result (about 2 seconds per company)."
    )
    if st.button("Check all companies"):
        companies = config.load_yaml("target_companies.yaml").get("companies") or []
        with st.status("Checking career boards...", expanded=True) as status:
            verify_companies.verify(companies, on_progress=st.write)
            verify_companies.save(companies)
            ok = sum(c["verified"] for c in companies)
            status.update(label=f"{ok} of {len(companies)} boards answered with jobs.", state="complete")
    companies = config.load_yaml("target_companies.yaml").get("companies") or []
    st.dataframe(
        [{"Company": c["name"], "ATS": c["ats"], "Tier": c.get("tier", ""), "On": c.get("enabled", True),
          "Verified": c.get("verified", False), "Open jobs": c.get("open_jobs"),
          "Checked": c.get("checked_on", ""), "Note": c.get("note", "")} for c in companies],
        width="stretch", hide_index=True,
    )

# --------------------------------------------------------------------- Jobs
with tab_jobs:
    jobs = db.list_jobs(conn)
    if not jobs:
        st.info("No jobs yet. Use **Fetch jobs** or **Add a job**.")
    else:
        f1, f2, f3 = st.columns([2, 2, 1])
        search = f1.text_input("Search title or company")
        sources = sorted({s for j in jobs for s in (j["seen_on"] or j["source"]).split(",")})
        picked = f2.multiselect("Source", sources)
        hide_abroad = f3.checkbox("Hide abroad", value=True)

        def keep(j):
            if hide_abroad and j["is_abroad"]:
                return False
            if picked and not set((j["seen_on"] or j["source"]).split(",")) & set(picked):
                return False
            text = f"{j['title']} {j['company']}".lower()
            return search.lower() in text

        shown = [j for j in jobs if keep(j)]
        dupes = db.count_duplicate_keys(conn)
        st.caption(f"Showing {len(shown)} of {len(jobs)} job(s). Duplicates in database: {dupes}.")
        table = [
            {
                "ID": j["id"],
                "Title": j["title"],
                "Company": j["company"],
                "Location": j["location"] or "",
                "Tags": ", ".join(t for t, on in [("remote", j["is_remote"]), ("abroad", j["is_abroad"])] if on),
                "Salary": j["salary_text"] or "",
                "Experience": j["experience_text"] or "",
                "Seen on": j["seen_on"] or j["source"],
                "Posted": j["posted_date"] or "",
                "Status": j["status"],
                "Added (UTC)": j["first_seen"].replace("T", " ")[:16],
            }
            for j in shown
        ]
        st.dataframe(table, width="stretch", hide_index=True)

        if shown:
            st.subheader("Job detail")
            labels = {j["id"]: f"#{j['id']} {j['title']} at {j['company']}" for j in shown}
            choice = st.selectbox("Pick a job", options=list(labels), format_func=labels.get)
            job = db.get_job(conn, choice)
            if job:
                st.markdown(f"**{job['title']}** at **{job['company']}**, {job['location'] or 'location not given'}")
                for link in db.get_job_urls(conn, choice):
                    if link["url"]:
                        st.markdown(f"- [{link['source']}]({link['url']})")
                st.text_area("Job description", job["description"] or "(no JD text saved)",
                             height=300, disabled=True)
