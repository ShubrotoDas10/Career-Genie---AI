import streamlit as st
import json
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from shared.db import (get_seeker_profile, get_applications_by_seeker,
                        get_interviews_by_seeker, get_unread_count,
                        get_skill_gap_history)
from shared.analytics import radar_chart, interview_scorecard

SKILL_CATEGORIES = {
    "Backend": ["Python", "Java", "Node.js", "Django", "FastAPI", "Spring", "Go", "REST", "GraphQL"],
    "Frontend": ["React", "Vue", "Angular", "HTML", "CSS", "JavaScript", "TypeScript", "Next.js"],
    "Data & ML": ["Machine Learning", "TensorFlow", "PyTorch", "Pandas", "NumPy", "SQL", "Spark", "Tableau"],
    "DevOps": ["Docker", "Kubernetes", "AWS", "Azure", "GCP", "CI/CD", "Terraform", "Linux", "Git"],
    "Soft Skills": ["Communication", "Leadership", "Problem Solving", "Teamwork", "Agile", "Scrum"],
    "Mobile": ["Android", "iOS", "Flutter", "React Native", "Swift", "Kotlin"],
}


def show_seeker_dashboard(user: dict):
    st.markdown(f"## 👋 Welcome back, **{user['name']}**!")
    st.markdown("---")

    profile = get_seeker_profile(user['id'])
    apps = get_applications_by_seeker(user['id'])
    interviews = get_interviews_by_seeker(user['id'])
    completed_interviews = [i for i in interviews if i.get('status') == 'completed']
    unread = get_unread_count(user['id'])
    gap_history = get_skill_gap_history(user['id'], limit=20)

    skills = []
    if profile:
        raw = profile.get('extracted_skills', [])
        skills = json.loads(raw) if isinstance(raw, str) else (raw or [])

    # ── KPI Row ────────────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("📄 Resume", "✅" if profile and profile.get('resume_text') else "❌ Missing")
    col2.metric("🎯 Skills", len(skills))
    col3.metric("📋 Applied", len(apps))
    col4.metric("🟢 Shortlisted", len([a for a in apps if a.get('status') == 'shortlisted']))
    col5.metric("🎤 Interviews", len(completed_interviews))
    col6.metric("📬 Unread", unread)

    if not profile or not profile.get('resume_text'):
        st.markdown("---")
        st.warning("⚠️ Upload your resume to unlock full dashboard analytics!")
        if st.button("📄 Upload Resume Now", type="primary"):
            st.session_state['seeker_page'] = 'resume'
            st.rerun()
        return

    st.markdown("---")

    # ── Row 1: Radar + Applications ───────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🕸️ Skill Coverage Radar")
        if skills:
            fig = radar_chart(skills, SKILL_CATEGORIES)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No skills extracted yet.")

    with col2:
        st.markdown("### 📋 Application Status Breakdown")
        if apps:
            status_counts = {}
            for a in apps:
                s = a.get('status', 'applied')
                status_counts[s] = status_counts.get(s, 0) + 1

            status_colors = {
                'applied': '#6366f1', 'reviewed': '#f59e0b', 'shortlisted': '#10b981',
                'rejected': '#ef4444', 'hired': '#8b5cf6'
            }
            fig_pie = go.Figure(go.Pie(
                labels=[s.capitalize() for s in status_counts.keys()],
                values=list(status_counts.values()),
                hole=0.5,
                marker_colors=[status_colors.get(s, '#6b7280') for s in status_counts.keys()],
                textinfo='label+value'
            ))
            fig_pie.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                                   paper_bgcolor='rgba(0,0,0,0)', showlegend=True)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No applications yet.")
            if st.button("🔍 Browse Jobs"):
                st.session_state['seeker_page'] = 'jobs'
                st.rerun()

    st.markdown("---")

    # ── Row 2: Match Score Trend + Skill Gap Progress ─────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📈 Match Score Trend (by Role)")
        if gap_history:
            df_gap = pd.DataFrame([{
                'Date': str(h['created_at'])[:10],
                'Role': h['target_role'][:25],
                'Score': round(h['match_score'] or 0)
            } for h in gap_history])
            fig_line = px.line(df_gap, x='Date', y='Score', color='Role',
                               markers=True, color_discrete_sequence=px.colors.qualitative.Set2)
            fig_line.update_layout(
                height=280, paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(248,248,248,0.05)',
                yaxis=dict(range=[0, 100], title="Match %"),
                legend=dict(font=dict(size=10))
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Run a Skill Gap Analysis to see your score trend here.")

    with col2:
        st.markdown("### 🔥 Skills Missing vs Matched (Latest)")
        if gap_history:
            latest = gap_history[0]
            matched = json.loads(latest['matched_skills']) if isinstance(latest['matched_skills'], str) else (latest.get('matched_skills') or [])
            missing = json.loads(latest['missing_skills']) if isinstance(latest['missing_skills'], str) else (latest.get('missing_skills') or [])

            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                name="✅ Matched", x=["Skills"],
                y=[len(matched)], marker_color='#10b981',
                text=[len(matched)], textposition='inside'
            ))
            fig_bar.add_trace(go.Bar(
                name="❌ Missing", x=["Skills"],
                y=[len(missing)], marker_color='#ef4444',
                text=[len(missing)], textposition='inside'
            ))
            fig_bar.update_layout(
                barmode='stack', height=280,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(248,248,248,0.05)',
                showlegend=True, margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            st.caption(f"For role: **{latest['target_role']}** | Last analyzed: {str(latest['created_at'])[:10]}")
        else:
            st.info("No skill gap data yet.")

    st.markdown("---")

    # ── Row 3: Interview Performance + Before/After ────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🎤 Interview Performance History")
        if completed_interviews:
            iv_data = []
            for iv in completed_interviews[:8]:
                max_s = iv.get('max_score', 1) or 1
                pct = round(iv.get('total_score', 0) / max_s * 100)
                iv_data.append({
                    'Job': (iv.get('job_title') or 'Interview')[:20],
                    'Score %': pct,
                    'Date': str(iv.get('completed_at', ''))[:10]
                })
            df_iv = pd.DataFrame(iv_data)
            fig_iv = px.bar(df_iv, x='Job', y='Score %', color='Score %',
                            color_continuous_scale=['#ef4444', '#f59e0b', '#10b981'],
                            range_color=[0, 100], text='Score %')
            fig_iv.update_traces(texttemplate='%{text}%', textposition='outside')
            fig_iv.update_layout(
                height=280, paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(248,248,248,0.05)',
                coloraxis_showscale=False,
                xaxis_tickangle=-25
            )
            st.plotly_chart(fig_iv, use_container_width=True)
        else:
            st.info("No completed interviews yet.")

    with col2:
        st.markdown("### 🔄 Before vs After Improvement")
        # Compare first and latest gap analysis for any role
        if len(gap_history) >= 2:
            roles_seen = {}
            for h in gap_history:
                r = h['target_role']
                if r not in roles_seen:
                    roles_seen[r] = []
                roles_seen[r].append(h)

            # Find a role with 2+ entries
            improvement_data = []
            for role, entries in roles_seen.items():
                if len(entries) >= 2:
                    first = entries[-1]
                    latest = entries[0]
                    improvement_data.append({
                        'Role': role[:20],
                        'First Score': round(first.get('match_score') or 0),
                        'Latest Score': round(latest.get('match_score') or 0),
                        'Improvement': round((latest.get('match_score') or 0) - (first.get('match_score') or 0))
                    })

            if improvement_data:
                df_imp = pd.DataFrame(improvement_data)
                fig_imp = go.Figure()
                fig_imp.add_trace(go.Bar(name='First Analysis', x=df_imp['Role'],
                                          y=df_imp['First Score'], marker_color='#6366f180'))
                fig_imp.add_trace(go.Bar(name='Latest Analysis', x=df_imp['Role'],
                                          y=df_imp['Latest Score'], marker_color='#10b981'))
                fig_imp.update_layout(
                    barmode='group', height=280,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(248,248,248,0.05)',
                    yaxis=dict(range=[0, 100]),
                    legend=dict(orientation='h', y=1.1)
                )
                st.plotly_chart(fig_imp, use_container_width=True)
            else:
                st.info("Analyze the same role twice to see improvement here.")
        else:
            st.info("Run skill gap analysis multiple times to track improvement.")

    st.markdown("---")

    # ── Row 4: Where You Lack + What to Improve ────────────────────────────────
    if gap_history:
        latest_gap = gap_history[0]
        gap_analysis_raw = latest_gap.get('gap_analysis', {})
        gap_analysis = json.loads(gap_analysis_raw) if isinstance(gap_analysis_raw, str) else (gap_analysis_raw or {})
        gap_items = gap_analysis.get('gap_analysis', []) if isinstance(gap_analysis, dict) else []

        if gap_items:
            st.markdown("### 🎯 Where You Lack — Priority Breakdown")
            st.caption(f"Based on your latest analysis for: **{latest_gap['target_role']}**")

            col1, col2 = st.columns(2)

            with col1:
                # Category breakdown
                cat_counts = {}
                for item in gap_items:
                    cat = item.get('category', 'General')
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1

                fig_cat = px.pie(
                    values=list(cat_counts.values()),
                    names=list(cat_counts.keys()),
                    title="Gaps by Category",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_cat.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)',
                                       margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig_cat, use_container_width=True)

            with col2:
                # Priority breakdown
                imp_counts = {'High': 0, 'Medium': 0, 'Low': 0}
                for item in gap_items:
                    imp = item.get('importance', 'Medium')
                    imp_counts[imp] = imp_counts.get(imp, 0) + 1

                fig_imp = go.Figure(go.Bar(
                    x=list(imp_counts.keys()),
                    y=list(imp_counts.values()),
                    marker_color=['#ef4444', '#f59e0b', '#3b82f6'],
                    text=list(imp_counts.values()),
                    textposition='outside'
                ))
                fig_imp.update_layout(
                    title="Gaps by Priority",
                    height=300, paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(248,248,248,0.05)',
                    margin=dict(l=10,r=10,t=40,b=10)
                )
                st.plotly_chart(fig_imp, use_container_width=True)

            # Top 3 things to work on
            st.markdown("### 🚀 Top 3 Things to Improve Right Now")
            high_priority = [i for i in gap_items if i.get('importance') == 'High'][:3]
            if not high_priority:
                high_priority = gap_items[:3]

            for item in high_priority:
                col1, col2, col3 = st.columns([2, 3, 2])
                with col1:
                    st.markdown(
                        f'<div style="background:#ef444415;border:1px solid #ef444440;'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:1.2em;font-weight:bold;color:#ef4444;">{item["skill"]}</div>'
                        f'<div style="color:#9ca3af;font-size:0.8em;">{item.get("category","")}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                with col2:
                    st.markdown(f"**Why:** {item.get('why_needed','')[:120]}")
                    st.markdown(f"**Fix:** {item.get('how_to_improve','')[:120]}")
                with col3:
                    st.info(f"⏱️ {item.get('estimated_time','')}")
                st.markdown("")

    st.markdown("---")

    # ── Quick Actions ──────────────────────────────────────────────────────────
    st.markdown("### ⚡ Quick Actions")
    c1, c2, c3, c4, c5 = st.columns(5)
    actions = [
        ("📄 Update Resume", 'resume'),
        ("🔍 Browse Jobs", 'jobs'),
        ("📊 Skill Gap", 'gap'),
        ("🎤 Practice Interview", 'interview'),
        ("💬 Messages", 'messages'),
    ]
    for col, (label, page) in zip([c1, c2, c3, c4, c5], actions):
        with col:
            if st.button(label, use_container_width=True):
                st.session_state['seeker_page'] = page
                st.rerun()
