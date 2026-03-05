import streamlit as st
import json
from shared.db import create_job, get_jobs_by_provider, toggle_job_status, get_job_by_id
from shared.groq_client import extract_skills_from_jd


def show_post_job(user: dict):
    st.markdown("## 📢 Post a Job")
    st.markdown("---")

    tab1, tab2 = st.tabs(["➕ New Job Posting", "📋 My Postings"])

    with tab1:
        _new_job_form(user)

    with tab2:
        _my_postings(user)


def _new_job_form(user: dict):
    st.markdown("### Job Details")

    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Job Title *", placeholder="e.g. Senior Python Developer")
        location = st.text_input("Location", placeholder="e.g. Mumbai / Remote")
    with col2:
        experience_level = st.selectbox("Experience Level", ["Entry", "Mid", "Senior", "Lead", "Manager"])
        tech_stack_input = st.text_input("Tech Stack (comma-separated)", placeholder="Python, FastAPI, PostgreSQL, Docker")

    description = st.text_area("Job Description *", height=200,
                                placeholder="Describe the role, responsibilities, requirements...")

    required_skills_input = st.text_input("Required Skills (comma-separated, or leave blank to auto-extract)",
                                           placeholder="Python, SQL, REST APIs, Git")

    st.markdown("---")
    st.markdown("### 🎤 Interview Configuration")
    st.markdown("Configure the AI-generated interview for applicants.")

    col1, col2, col3 = st.columns(3)
    with col1:
        behavioral_count = st.number_input("Behavioral Questions", min_value=0, max_value=10, value=3)
        marks_per_behavioral = st.number_input("Marks per Behavioral Q", min_value=1, max_value=20, value=5)

    with col2:
        technical_count = st.number_input("Technical Questions", min_value=0, max_value=15, value=5)
        marks_per_technical = st.number_input("Marks per Technical Q", min_value=1, max_value=30, value=10)

    with col3:
        coding_count = st.number_input("Coding Questions", min_value=0, max_value=10, value=2)
        marks_per_coding = st.number_input("Marks per Coding Q", min_value=1, max_value=50, value=15)

    col4, col5 = st.columns(2)
    with col4:
        difficulty = st.selectbox("Interview Difficulty", ["Easy", "Medium", "Hard"])
    with col5:
        total_marks = (behavioral_count * marks_per_behavioral +
                       technical_count * marks_per_technical +
                       coding_count * marks_per_coding)
        passing_marks = st.number_input("Passing Marks", min_value=0,
                                         max_value=int(total_marks) if total_marks > 0 else 100,
                                         value=int(total_marks * 0.6) if total_marks > 0 else 0)

    st.info(f"📊 **Total Marks:** {total_marks} | **Passing Marks:** {passing_marks} | "
            f"**Total Questions:** {behavioral_count + technical_count + coding_count}")

    st.markdown("---")
    if st.button("📢 Post Job", type="primary", use_container_width=True):
        if not title or not description:
            st.error("❌ Job title and description are required.")
            return

        tech_stack = [t.strip() for t in tech_stack_input.split(',') if t.strip()] if tech_stack_input else []

        with st.spinner("Extracting required skills from description..."):
            if required_skills_input.strip():
                req_skills = [s.strip() for s in required_skills_input.split(',') if s.strip()]
            else:
                req_skills = extract_skills_from_jd(description)
                if tech_stack:
                    req_skills = list(set(req_skills + tech_stack))

        interview_config = {
            "behavioral_count": behavioral_count,
            "technical_count": technical_count,
            "coding_count": coding_count,
            "marks_per_behavioral": marks_per_behavioral,
            "marks_per_technical": marks_per_technical,
            "marks_per_coding": marks_per_coding,
            "difficulty": difficulty,
            "passing_marks": passing_marks,
            "total_marks": total_marks,
        }

        try:
            job_id = create_job(
                provider_id=user['id'],
                title=title,
                description=description,
                required_skills=req_skills,
                tech_stack=tech_stack,
                experience_level=experience_level,
                location=location,
                interview_config=interview_config
            )
            st.success(f"✅ Job posted successfully! (ID: {job_id})")
            st.markdown(f"**Auto-extracted {len(req_skills)} required skills:** {', '.join(req_skills[:10])}")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Error posting job: {e}")


def _my_postings(user: dict):
    jobs = get_jobs_by_provider(user['id'])
    if not jobs:
        st.info("You haven't posted any jobs yet.")
        return

    st.markdown(f"**{len(jobs)} job posting(s)**")
    for job in jobs:
        status = "🟢 Active" if job.get('is_active') else "🔴 Inactive"
        config = job.get('interview_config', {})
        if isinstance(config, str):
            config = json.loads(config)

        with st.expander(f"{status} | **{job['title']}** | 📍 {job.get('location', 'N/A')} | "
                         f"Posted: {str(job.get('created_at',''))[:10]}"):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Behavioral Qs", config.get('behavioral_count', 0))
            col2.metric("Technical Qs", config.get('technical_count', 0))
            col3.metric("Coding Qs", config.get('coding_count', 0))
            col4.metric("Total Marks", config.get('total_marks', 0))

            req_skills = job.get('required_skills', [])
            if isinstance(req_skills, str):
                req_skills = json.loads(req_skills)
            if req_skills:
                st.markdown(f"**Required Skills:** {', '.join(req_skills[:8])}")

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("👥 View Candidates", key=f"cands_{job['id']}"):
                    st.session_state['view_job_id'] = job['id']
                    st.session_state['provider_page'] = 'candidates'
                    st.rerun()
            with c2:
                label = "⏸️ Deactivate" if job.get('is_active') else "▶️ Activate"
                if st.button(label, key=f"toggle_{job['id']}"):
                    toggle_job_status(job['id'], not job.get('is_active'))
                    st.rerun()
