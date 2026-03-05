import streamlit as st
import json
from shared.resume_parser import parse_resume, save_resume_file
from shared.groq_client import extract_skills_from_resume
from shared.db import upsert_seeker_profile, get_seeker_profile


def show_resume_upload(user: dict):
    st.markdown("## 📄 Resume Upload & Skill Extraction")
    st.markdown("Upload your resume and we'll automatically extract your skills using AI.")
    st.markdown("---")

    # Show existing profile
    profile = get_seeker_profile(user['id'])
    if profile and profile.get('resume_file_name'):
        st.success(f"✅ Resume on file: **{profile['resume_file_name']}**")
        skills = profile.get('extracted_skills', [])
        if isinstance(skills, str):
            skills = json.loads(skills)
        if skills:
            st.markdown(f"**{len(skills)} skills extracted:**")
            _render_skill_tags(skills)
        st.markdown("---")
        st.markdown("**Upload a new resume to replace:**")

    uploaded = st.file_uploader(
        "Choose your resume",
        type=["pdf", "docx"],
        help="Supported formats: PDF, DOCX"
    )

    if uploaded:
        st.info(f"📎 File selected: **{uploaded.name}** ({round(uploaded.size/1024, 1)} KB)")

        if st.button("⚙️ Extract Skills", type="primary", use_container_width=True):
            with st.spinner("Parsing resume..."):
                try:
                    file_bytes = uploaded.getvalue()
                    # Re-create file-like object for parser
                    import io
                    file_obj = io.BytesIO(file_bytes)
                    file_obj.name = uploaded.name
                    file_obj.read = file_obj.read

                    # Parse
                    if uploaded.name.lower().endswith('.pdf'):
                        from shared.resume_parser import extract_text_from_pdf
                        resume_text = extract_text_from_pdf(file_bytes)
                        ext = "pdf"
                    else:
                        from shared.resume_parser import extract_text_from_docx
                        resume_text = extract_text_from_docx(file_bytes)
                        ext = "docx"

                    if not resume_text.strip():
                        st.error("❌ Could not extract text from the file. Please try another format.")
                        return

                except Exception as e:
                    st.error(f"❌ Error parsing resume: {e}")
                    return

            with st.spinner("🤖 AI is analyzing your resume..."):
                try:
                    parsed = extract_skills_from_resume(resume_text)
                except Exception as e:
                    st.error(f"❌ AI extraction failed: {e}")
                    return

            # Save to DB
            try:
                skills = parsed.get('skills', [])
                upsert_seeker_profile(user['id'], resume_text, skills, uploaded.name)
                save_resume_file(file_bytes, user['id'], ext)
            except Exception as e:
                st.warning(f"⚠️ Could not save to database: {e}")

            # Display results
            st.success("✅ Resume analyzed successfully!")
            st.markdown("---")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Skills Found", len(parsed.get('skills', [])))
            col2.metric("Experience", f"{parsed.get('experience_years', 0)} yrs")
            col3.metric("Education", parsed.get('education', 'N/A')[:20] + "..." if len(parsed.get('education', '')) > 20 else parsed.get('education', 'N/A'))
            col4.metric("Roles", len(parsed.get('job_titles', [])))

            st.markdown("### 🎯 Extracted Skills")
            _render_skill_tags(parsed.get('skills', []))

            if parsed.get('job_titles'):
                st.markdown("### 💼 Previous Roles")
                for title in parsed.get('job_titles', []):
                    st.markdown(f"- {title}")

            if parsed.get('summary'):
                st.markdown("### 📝 AI Summary")
                st.info(parsed['summary'])

            st.session_state['seeker_skills'] = parsed.get('skills', [])
            st.session_state['resume_parsed'] = parsed


def _render_skill_tags(skills: list):
    """Render skills as colored tags."""
    if not skills:
        st.caption("No skills found.")
        return
    cols = st.columns(6)
    colors = ["#6366f1", "#8b5cf6", "#ec4899", "#10b981", "#f59e0b", "#3b82f6"]
    for i, skill in enumerate(skills):
        col = cols[i % 6]
        color = colors[i % len(colors)]
        col.markdown(
            f'<span style="background:{color}20;color:{color};border:1px solid {color}40;'
            f'padding:3px 10px;border-radius:20px;font-size:0.82em;display:inline-block;'
            f'margin:2px;">{skill}</span>',
            unsafe_allow_html=True
        )
