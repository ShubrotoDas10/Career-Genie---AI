import streamlit as st
import json
from shared.db import (get_all_active_jobs, get_seeker_profile, apply_to_job,
                        get_application, get_applications_by_seeker, get_job_by_id)
from shared.groq_client import compute_match_score, extract_skills_from_jd
from shared.analytics import match_score_gauge, skill_gap_heatmap


def show_job_match(user: dict):
    st.markdown("## 🎯 Job Matching")
    st.markdown("---")

    profile = get_seeker_profile(user['id'])
    if not profile or not profile.get('resume_text'):
        st.warning("⚠️ Please upload your resume first before matching with jobs.")
        if st.button("📄 Go to Resume Upload"):
            st.session_state['seeker_page'] = 'resume'
            st.rerun()
        return

    seeker_skills = profile.get('extracted_skills', [])
    if isinstance(seeker_skills, str):
        seeker_skills = json.loads(seeker_skills)

    tab1, tab2 = st.tabs(["🔍 Browse Jobs", "📋 My Applications"])

    with tab1:
        _browse_jobs(user, seeker_skills)

    with tab2:
        _my_applications(user)


def _browse_jobs(user: dict, seeker_skills: list):
    jobs = get_all_active_jobs()
    if not jobs:
        st.info("No active job postings at the moment. Check back later!")
        return

    # Filters
    col1, col2 = st.columns([3, 1])
    with col1:
        search = st.text_input("🔎 Search jobs", placeholder="e.g. Python, Data Science, React...")
    with col2:
        sort_by = st.selectbox("Sort by", ["Latest", "Match Score"])

    if search:
        jobs = [j for j in jobs if search.lower() in j['title'].lower()
                or search.lower() in j['description'].lower()]

    st.markdown(f"**{len(jobs)} job(s) found**")
    st.markdown("---")

    # Pre-compute match scores
    for job in jobs:
        req_skills = job.get('required_skills', [])
        if isinstance(req_skills, str):
            req_skills = json.loads(req_skills)
        already_applied = get_application(user['id'], job['id'])
        job['_applied'] = bool(already_applied)
        job['_match_score'] = already_applied.get('match_score', 0) if already_applied else None
        job['_req_skills'] = req_skills

    if sort_by == "Match Score":
        jobs = sorted(jobs, key=lambda j: j.get('_match_score') or 0, reverse=True)

    for job in jobs:
        _job_card(user, job, seeker_skills)


def _job_card(user: dict, job: dict, seeker_skills: list):
    req_skills = job.get('_req_skills', [])
    tech_stack = job.get('tech_stack', [])
    if isinstance(tech_stack, str):
        tech_stack = json.loads(tech_stack)

    with st.expander(f"**{job['title']}** — {job.get('company_name') or job.get('provider_name', 'Company')} | 📍 {job.get('location', 'Remote')}", expanded=False):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**Description:**")
            st.markdown(job['description'][:400] + ("..." if len(job['description']) > 400 else ""))

            if req_skills:
                st.markdown("**Required Skills:**")
                st.markdown(" ".join([f"`{s}`" for s in req_skills[:12]]))

            if tech_stack:
                st.markdown("**Tech Stack:**")
                st.markdown(" ".join([f"`{t}`" for t in tech_stack]))

        with col2:
            if job['_applied']:
                st.success("✅ Applied")
                if job['_match_score']:
                    st.plotly_chart(match_score_gauge(job['_match_score']),
                                    use_container_width=True, key=f"gauge_{job['id']}")
            else:
                if st.button("🚀 Analyze & Apply", key=f"apply_{job['id']}", type="primary"):
                    _analyze_and_apply(user, job, seeker_skills, req_skills)


def _analyze_and_apply(user: dict, job: dict, seeker_skills: list, req_skills: list):
    with st.spinner("🤖 Computing match score..."):
        try:
            if not req_skills:
                req_skills = extract_skills_from_jd(job['description'])
            result = compute_match_score(seeker_skills, req_skills, job['description'])
            score = result.get('score', 0)
            apply_to_job(user['id'], job['id'], score)
            st.success(f"✅ Applied! Match Score: **{score}%**")
            st.plotly_chart(match_score_gauge(score), use_container_width=True, key=f"gauge_new_{job['id']}")

            if result.get('missing_skills'):
                st.warning(f"Missing skills: {', '.join(result['missing_skills'][:5])}")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")


def _my_applications(user: dict):
    apps = get_applications_by_seeker(user['id'])
    if not apps:
        st.info("You haven't applied to any jobs yet.")
        return

    st.markdown(f"**{len(apps)} application(s)**")
    for app in apps:
        status_color = {
            'applied': '🔵', 'reviewed': '🟡', 'shortlisted': '🟢',
            'rejected': '🔴', 'hired': '🏆'
        }.get(app.get('status', 'applied'), '⚪')

        with st.expander(f"{status_color} **{app['title']}** — {app.get('company_name', '')} | Match: {round(app.get('match_score', 0))}%"):
            col1, col2, col3 = st.columns(3)
            col1.metric("Match Score", f"{round(app.get('match_score', 0))}%")
            col2.metric("Status", app.get('status', 'Applied').capitalize())
            col3.metric("Applied", str(app.get('applied_at', ''))[:10])

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("💬 Message Provider", key=f"msg_{app['id']}"):
                    st.session_state['message_to'] = app.get('provider_id')
                    st.session_state['message_job_id'] = app.get('job_id')
                    st.session_state['seeker_page'] = 'messages'
                    st.rerun()
            with col_b:
                if st.button("🎤 Start Interview", key=f"interview_{app['id']}"):
                    st.session_state['interview_job_id'] = app['job_id']
                    st.session_state['interview_app_id'] = app['id']
                    st.session_state['seeker_page'] = 'interview'
                    st.rerun()
