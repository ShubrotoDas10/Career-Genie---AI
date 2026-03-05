import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Career Genie 🧞",
    page_icon="🧞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize DB on startup
@st.cache_resource
def init_database():
    try:
        from shared.db import init_db
        init_db()
        return True
    except Exception as e:
        return str(e)

db_status = init_database()

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Main header */
    .main-header {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%);
        padding: 20px 30px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
    }

    /* Metric cards */
    div[data-testid="metric-container"] {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }

    /* Sidebar nav buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
    }
</style>
""", unsafe_allow_html=True)


def show_landing():
    """Landing page with login/signup options."""
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;font-size:2.5em;">🧞 Career Genie</h1>
        <p style="margin:8px 0 0 0;font-size:1.1em;opacity:0.9;">
            AI-powered career platform connecting talent with opportunity
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Welcome! Choose an option to get started.")
        st.markdown("")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔑 Login", use_container_width=True, type="primary"):
                st.session_state['show_login'] = True
                st.session_state['show_signup'] = False
                st.rerun()
        with c2:
            if st.button("📝 Sign Up", use_container_width=True):
                st.session_state['show_signup'] = True
                st.session_state['show_login'] = False
                st.rerun()

        st.markdown("---")
        st.markdown("#### ✨ Features")
        st.markdown("""
        **For Job Seekers:**
        - 📄 AI-powered resume parsing
        - 🎯 Smart job matching with score
        - 📊 Skill gap analysis & heatmap
        - 🗺️ Personalized upskilling roadmap
        - 🎤 Custom AI mock interviews
        - 💬 Direct messaging with providers

        **For Job Providers:**
        - 📢 Post jobs with AI skill extraction
        - 🎤 Custom interview builder (behavioral + technical + coding)
        - 🏆 AI-ranked candidate list
        - 📊 Analytics dashboard
        - 📥 Resume download
        - 💬 Direct messaging with candidates
        """)


def show_seeker_app(user: dict):
    """Seeker-side navigation and routing."""
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        st.markdown(f"*Job Seeker*")
        st.markdown("---")

        pages = {
            "🏠 Dashboard": "dashboard",
            "📄 My Resume": "resume",
            "🔍 Browse Jobs": "jobs",
            "📊 Skill Gap": "gap",
            "🎤 Interview": "interview",
            "💬 Messages": "messages",
        }
        for label, key in pages.items():
            if st.button(label, use_container_width=True, key=f"nav_{key}"):
                st.session_state['seeker_page'] = key
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    page = st.session_state.get('seeker_page', 'dashboard')

    if page == 'dashboard':
        from seeker.dashboard import show_seeker_dashboard
        show_seeker_dashboard(user)
    elif page == 'resume':
        from seeker.resume_upload import show_resume_upload
        show_resume_upload(user)
    elif page == 'jobs':
        from seeker.job_match import show_job_match
        show_job_match(user)
    elif page == 'gap':
        from seeker.skill_gap import show_skill_gap
        show_skill_gap(user)
    elif page == 'interview':
        from seeker.interview_room import show_interview_room
        show_interview_room(user)
    elif page == 'messages':
        from seeker.messages import show_seeker_messages
        show_seeker_messages(user)


def show_provider_app(user: dict):
    """Provider-side navigation and routing."""
    with st.sidebar:
        st.markdown(f"### 🏢 {user['name']}")
        st.markdown(f"*Job Provider*")
        st.markdown("---")

        pages = {
            "🏠 Dashboard": "dashboard",
            "📢 Post a Job": "post_job",
            "👥 Candidates": "candidates",
            "💬 Messages": "messages",
        }
        for label, key in pages.items():
            if st.button(label, use_container_width=True, key=f"pnav_{key}"):
                st.session_state['provider_page'] = key
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    page = st.session_state.get('provider_page', 'dashboard')

    if page == 'dashboard':
        from provider.dashboard import show_provider_dashboard
        show_provider_dashboard(user)
    elif page == 'post_job':
        from provider.post_job import show_post_job
        show_post_job(user)
    elif page == 'candidates':
        from provider.candidates import show_candidates
        show_candidates(user)
    elif page == 'messages':
        from provider.messages import show_provider_messages
        show_provider_messages(user)


def main():
    # DB error check
    if isinstance(db_status, str):
        st.error(f"❌ Database connection failed: {db_status}")
        st.info("Please check your `.env` file and ensure PostgreSQL is running.")
        st.code("""
# .env file should contain:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=career_genie
DB_USER=postgres
DB_PASSWORD=your_password
GROQ_API_KEY=your_groq_key
        """)
        return

    user = st.session_state.get('user')

    if not user:
        if st.session_state.get('show_login'):
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown("""
                <div style="text-align:center;padding:20px 0;">
                    <h2>🧞 Career Genie</h2>
                </div>
                """, unsafe_allow_html=True)
                from auth.login import show_login
                show_login()
        elif st.session_state.get('show_signup'):
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown("""
                <div style="text-align:center;padding:20px 0;">
                    <h2>🧞 Career Genie</h2>
                </div>
                """, unsafe_allow_html=True)
                from auth.signup import show_signup
                show_signup()
        else:
            show_landing()
    else:
        # Route based on role
        if user['role'] == 'seeker':
            show_seeker_app(user)
        elif user['role'] == 'provider':
            show_provider_app(user)
        else:
            st.error("Unknown user role.")
            if st.button("Logout"):
                st.session_state.clear()
                st.rerun()


if __name__ == "__main__":
    main()
