import streamlit as st
import json
import os
from shared.db import (get_jobs_by_provider, get_applications_by_job,
                        update_application_status, get_job_by_id)
from shared.analytics import candidate_ranking_table


def show_candidates(user: dict):
    st.markdown("## 👥 Candidate Management")
    st.markdown("---")

    jobs = get_jobs_by_provider(user['id'])
    if not jobs:
        st.info("Post a job first to see candidates.")
        return

    # Job selector
    job_options = {f"{j['title']} (ID:{j['id']})": j['id'] for j in jobs}
    preselect = st.session_state.get('view_job_id')

    default_idx = 0
    if preselect:
        keys = list(job_options.keys())
        vals = list(job_options.values())
        if preselect in vals:
            default_idx = vals.index(preselect)

    selected_label = st.selectbox("Select Job Posting:", list(job_options.keys()), index=default_idx)
    job_id = job_options[selected_label]
    job = get_job_by_id(job_id)

    applications = get_applications_by_job(job_id)

    if not applications:
        st.info("No candidates have applied to this job yet.")
        return

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Filter by Status", ["All", "applied", "reviewed", "shortlisted", "rejected", "hired"])
    with col2:
        min_score = st.slider("Minimum Match Score", 0, 100, 0)
    with col3:
        st.metric("Total Applicants", len(applications))

    # Filter
    filtered = applications
    if status_filter != "All":
        filtered = [a for a in filtered if a.get('status') == status_filter]
    filtered = [a for a in filtered if a.get('match_score', 0) >= min_score]

    st.markdown(f"**Showing {len(filtered)} candidate(s)**")

    # Ranking Table
    st.markdown("### 🏆 Candidate Rankings")
    df = candidate_ranking_table(filtered)
    if not df.empty:
        display_df = df.drop(columns=[c for c in ['Email', 'App ID'] if c in df.columns], errors='ignore')
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 📋 Detailed Candidate Profiles")

    for app in filtered:
        skills = app.get('extracted_skills', [])
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except Exception:
                skills = []

        match_score = round(app.get('match_score', 0))
        score_color = '🟢' if match_score >= 70 else '🟡' if match_score >= 40 else '🔴'

        with st.expander(
            f"{score_color} **{app['seeker_name']}** | Match: {match_score}% | "
            f"Status: {app.get('status','applied').capitalize()} | {app.get('email','')}"
        ):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Email:** {app.get('email', 'N/A')}")
                st.markdown(f"**Skills ({len(skills)}):**")
                if skills:
                    st.markdown(" ".join([f"`{s}`" for s in skills[:15]]))

                if app.get('resume_text'):
                    with st.expander("📄 Resume Preview"):
                        st.text(app['resume_text'][:1500] + "..." if len(app.get('resume_text', '')) > 1500 else app.get('resume_text', ''))

            with col2:
                # Status update
                new_status = st.selectbox(
                    "Update Status",
                    ["applied", "reviewed", "shortlisted", "rejected", "hired"],
                    index=["applied", "reviewed", "shortlisted", "rejected", "hired"].index(
                        app.get('status', 'applied')
                    ),
                    key=f"status_{app['id']}"
                )
                if st.button("💾 Update", key=f"upd_{app['id']}"):
                    update_application_status(app['id'], new_status)
                    st.success("Status updated!")
                    st.rerun()

                # Resume download
                resume_file = app.get('resume_file_name', '')
                if resume_file:
                    seeker_id = app.get('seeker_id')
                    ext = 'pdf' if resume_file.endswith('.pdf') else 'docx'
                    file_path = f"uploads/resume_{seeker_id}.{ext}"
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            st.download_button(
                                "📥 Download Resume",
                                data=f.read(),
                                file_name=resume_file,
                                mime='application/pdf' if ext == 'pdf' else
                                     'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                key=f"dl_{app['id']}"
                            )

                # Message
                if st.button("💬 Message", key=f"msg_{app['id']}"):
                    st.session_state['message_to'] = app.get('seeker_id')
                    st.session_state['message_job_id'] = job_id
                    st.session_state['provider_page'] = 'messages'
                    st.rerun()
