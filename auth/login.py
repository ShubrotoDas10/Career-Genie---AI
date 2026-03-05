import streamlit as st
import bcrypt
from shared.db import get_user_by_email


def show_login():
    st.markdown("### 🔐 Welcome Back")
    st.markdown("---")

    email = st.text_input("Email Address", placeholder="john@example.com")
    password = st.text_input("Password", type="password")

    st.markdown("")
    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("🔑 Login", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("❌ Please enter email and password.")
                return

            user = get_user_by_email(email)
            if not user:
                st.error("❌ No account found with this email.")
                return

            if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
                st.error("❌ Incorrect password.")
                return

            # Set session
            st.session_state['user'] = {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role']
            }
            st.session_state['page'] = 'dashboard'
            st.success(f"✅ Welcome back, {user['name']}!")
            st.rerun()

    with col2:
        if st.button("← Back", use_container_width=True):
            st.session_state['show_login'] = False
            st.rerun()
