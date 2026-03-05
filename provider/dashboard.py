import streamlit as st
import json
import plotly.express as px
import pandas as pd
from shared.db import (get_jobs_by_provider, get_applications_by_job,
                        get_provider_profile, get_unread_count)


def show_provider_dashboard(user: dict):
    st.markdown(f"## 👋 Welcome, **{user['name']}**!")

    profile = get_provider_profile(user['id'])
    company = profile.get('company_name', '') if profile else ''
    if company:
        st.markdown(f"#### 🏢 {company}")
    st.markdown("---")

    jobs = get_jobs_by_provider(user['id'])
    active_jobs = [j for j in jobs if j.get('is_active')]
    unread = get_unread_count(user['id'])

    # KPIs
    all_apps = []
    for job in jobs:
        apps = get_applications_by_job(job['id'])
        for a in apps:
            a['_job_title'] = job['title']
        all_apps.extend(apps)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📢 Total Jobs", len(jobs))
    col2.metric("🟢 Active Jobs", len(active_jobs))
    col3.metric("👥 Total Applicants", len(all_apps))
    col4.metric("🟢 Shortlisted", len([a for a in all_apps if a.get('status') == 'shortlisted']))
    col5.metric("📬 Unread", unread)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📊 Applications by Job")
        if jobs:
            job_data = []
            for job in jobs[:8]:
                apps = get_applications_by_job(job['id'])
                job_data.append({'Job': job['title'][:30], 'Applications': len(apps)})
            df = pd.DataFrame(job_data)
            if not df.empty and df['Applications'].sum() > 0:
                fig = px.bar(df, x='Applications', y='Job', orientation='h',
                             color='Applications', color_continuous_scale='Viridis')
                fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=20),
                                   paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No applications yet.")

    with col2:
        st.markdown("### 🔵 Application Status Breakdown")
        if all_apps:
            status_counts = {}
            for a in all_apps:
                s = a.get('status', 'applied')
                status_counts[s] = status_counts.get(s, 0) + 1

            fig = px.pie(
                values=list(status_counts.values()),
                names=list(status_counts.keys()),
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=20),
                               paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No application data yet.")

    st.markdown("---")

    # Top candidates across all jobs
    if all_apps:
        st.markdown("### 🏆 Top Candidates (by Match Score)")
        top = sorted(all_apps, key=lambda a: a.get('match_score', 0), reverse=True)[:5]
        for i, app in enumerate(top):
            score = round(app.get('match_score', 0))
            color = '🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else '⭐'
            st.markdown(
                f"{color} **{app.get('seeker_name', 'Unknown')}** — "
                f"{app.get('_job_title', '')} | Match: `{score}%` | "
                f"Status: `{app.get('status', 'applied')}`"
            )

    st.markdown("---")
    st.markdown("### ⚡ Quick Actions")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("📢 Post New Job", use_container_width=True, type="primary"):
            st.session_state['provider_page'] = 'post_job'
            st.rerun()
    with c2:
        if st.button("👥 View Candidates", use_container_width=True):
            st.session_state['provider_page'] = 'candidates'
            st.rerun()
    with c3:
        if st.button("💬 Messages", use_container_width=True):
            st.session_state['provider_page'] = 'messages'
            st.rerun()
    with c4:
        if st.button("📋 My Postings", use_container_width=True):
            st.session_state['provider_page'] = 'post_job'
            st.rerun()
