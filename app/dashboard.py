"""Review dashboard (SPEC.md Section 7). Phase 1: add a job by hand, see the jobs table.

Start it from the project folder with:
    streamlit run app/dashboard.py
"""
import sys
from pathlib import Path

# Streamlit runs this file directly, so Python would not find the "core" and
# "collectors" folders. Adding the project root to the search path fixes that.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from collectors import manual  # noqa: E402
from core import config, db  # noqa: E402

st.set_page_config(page_title="Job Hunt Copilot", layout="wide")
st.title("Job Hunt Copilot")


@st.cache_resource
def get_conn():
    # One shared connection for the whole app, opened once.
    return db.connect(check_same_thread=False)


conn = get_conn()
tab_jobs, tab_add = st.tabs(["Jobs", "Add a job"])

# The 'Add a job' code runs first (even though its tab is shown second) so a
# job saved in this run already appears in the Jobs table below.
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
            job_id, is_new = db.save_job(conn, job)
            if is_new:
                st.success(f"Saved as job #{job_id}: {job.title} at {job.company}. See the Jobs tab.")
            else:
                st.info(f"Already had this job (#{job_id}); merged the new details into it.")

# --------------------------------------------------------------------- Jobs
with tab_jobs:
    jobs = db.list_jobs(conn)
    if not jobs:
        st.info("No jobs yet. Use the 'Add a job' tab to paste one.")
    else:
        st.caption(f"{len(jobs)} job(s) stored in {config.db_path()}")
        table = [
            {
                "ID": j["id"],
                "Title": j["title"],
                "Company": j["company"],
                "Location": j["location"] or "",
                "Tags": ", ".join(t for t, on in [("remote", j["is_remote"]), ("abroad", j["is_abroad"])] if on),
                "Salary": j["salary_text"] or "",
                "Experience": j["experience_text"] or "",
                "Source": j["source"],
                "Posted": j["posted_date"] or "",
                "Status": j["status"],
                "Added (UTC)": j["first_seen"].replace("T", " ")[:16],
            }
            for j in jobs
        ]
        st.dataframe(table, width="stretch", hide_index=True)

        st.subheader("Job detail")
        choice = st.selectbox(
            "Pick a job",
            options=[j["id"] for j in jobs],
            format_func=lambda i: next(f"#{j['id']} {j['title']} at {j['company']}" for j in jobs if j["id"] == i),
        )
        job = db.get_job(conn, choice)
        if job:
            st.markdown(f"**{job['title']}** at **{job['company']}**, {job['location'] or 'location not given'}")
            for link in db.get_job_urls(conn, choice):
                if link["url"]:
                    st.markdown(f"- [{link['source']}]({link['url']})")
            st.text_area("Job description", job["description"] or "(no JD text saved)", height=300, disabled=True)
