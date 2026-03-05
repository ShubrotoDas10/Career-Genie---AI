import streamlit as st
import bcrypt
from shared.db import create_user, get_user_by_email


def show_signup():
    st.markdown("### 📝 Create Your Account")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name", placeholder="John Doe")
        email = st.text_input("Email Address", placeholder="john@example.com")
        password = st.text_input("Password", type="password", placeholder="Min 6 characters")

    with col2:
        confirm_password = st.text_input("Confirm Password", type="password")
        role = st.selectbox("I am a...", ["", "Job Seeker", "Job Provider"],
                             format_func=lambda x: "Select your role" if x == "" else x)

        if role == "Job Provider":
            company = st.text_input("Company Name", placeholder="Acme Corp")
        else:
            company = ""

    st.markdown("")
    if st.button("🚀 Create Account", use_container_width=True, type="primary"):
        # Validation
        if not all([name, email, password, confirm_password, role]):
            st.error("❌ Please fill in all required fields.")
            return
        if password != confirm_password:
            st.error("❌ Passwords do not match.")
            return
        if len(password) < 6:
            st.error("❌ Password must be at least 6 characters.")
            return
        if role == "":
            st.error("❌ Please select your role.")
            return
        if get_user_by_email(email):
            st.error("❌ An account with this email already exists.")
            return

        role_key = "seeker" if role == "Job Seeker" else "provider"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        try:
            user_id = create_user(name, email, hashed, role_key)
            if role_key == "provider" and company:
                from shared.db import upsert_provider_profile
                upsert_provider_profile(user_id, company, "", "")

            st.success("✅ Account created successfully! Please log in.")
            st.session_state['show_login'] = True
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error creating account: {e}")
