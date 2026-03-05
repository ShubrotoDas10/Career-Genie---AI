import streamlit as st
import json
from shared.db import (get_seeker_profile, get_all_active_jobs, save_skill_gap,
                        get_skill_gap_history, get_latest_two_gaps,
                        upsert_roadmap_progress, get_roadmap_progress)
from shared.groq_client import (analyze_skill_gap, get_upskilling_recommendations,
                                  compute_match_score, extract_skills_from_jd,
                                  suggest_roles_from_resume)
from shared.analytics import skill_gap_heatmap, improvement_roadmap_chart, radar_chart
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

SKILL_CATEGORIES = {
    "Backend": ["Python", "Java", "Node.js", "Django", "FastAPI", "Spring", "Go", "REST", "GraphQL"],
    "Frontend": ["React", "Vue", "Angular", "HTML", "CSS", "JavaScript", "TypeScript", "Next.js"],
    "Data & ML": ["Machine Learning", "TensorFlow", "PyTorch", "Pandas", "NumPy", "SQL", "Spark", "Tableau"],
    "DevOps": ["Docker", "Kubernetes", "AWS", "Azure", "GCP", "CI/CD", "Terraform", "Linux", "Git"],
    "Soft Skills": ["Communication", "Leadership", "Problem Solving", "Teamwork", "Agile", "Scrum"],
    "Mobile": ["Android", "iOS", "Flutter", "React Native", "Swift", "Kotlin"],
}

LEVEL_COLORS = {
    "Intern":    "#10b981",
    "Junior":    "#3b82f6",
    "Mid-Level": "#f59e0b",
    "Senior":    "#ef4444",
    "All":       "#8b5cf6",
}

STATUS_CONFIG = {
    "not_started": ("⬜", "#6b7280", "Not Started"),
    "in_progress":  ("🔄", "#f59e0b", "In Progress"),
    "completed":    ("✅", "#10b981", "Completed"),
}


def show_skill_gap(user: dict):
    st.markdown("## 📊 Skill Gap Analysis")
    st.markdown("---")

    profile = get_seeker_profile(user['id'])
    if not profile or not profile.get('resume_text'):
        st.warning("⚠️ Please upload your resume first to unlock Skill Gap Analysis.")
        if st.button("📄 Upload Resume", type="primary"):
            st.session_state['seeker_page'] = 'resume'
            st.rerun()
        return

    seeker_skills = profile.get('extracted_skills', [])
    if isinstance(seeker_skills, str):
        seeker_skills = json.loads(seeker_skills)

    tab1, tab2, tab3 = st.tabs(["🎯 Analyze for a Role", "🗺️ Upskilling Roadmap", "📈 My Progress History"])

    with tab1:
        _job_gap_analysis(user, seeker_skills, profile)

    with tab2:
        _upskilling_roadmap(user, seeker_skills, profile)

    with tab3:
        _progress_history(user)


# ─── Tab 1: Gap Analysis ───────────────────────────────────────────────────────

def _job_gap_analysis(user: dict, seeker_skills: list, profile):
    st.markdown("### Choose a Role to Analyze Against")

    # ── Level filter buttons ──
    st.markdown("**Filter by career level:**")
    levels = ["All", "Intern", "Junior", "Mid-Level", "Senior"]
    selected_level = st.session_state.get('gap_level_filter', 'All')

    level_cols = st.columns(len(levels))
    for i, lvl in enumerate(levels):
        with level_cols[i]:
            color = LEVEL_COLORS[lvl]
            is_sel = selected_level == lvl
            if st.button(
                lvl,
                key=f"gap_lvl_{lvl}",
                use_container_width=True,
                type="primary" if is_sel else "secondary"
            ):
                st.session_state['gap_level_filter'] = lvl
                st.session_state.pop('gap_suggested_roles', None)  # refresh suggestions
                st.rerun()

    st.markdown("---")

    # ── Role selection ──
    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("**Option A: Pick from active job postings**")
        jobs = get_all_active_jobs()

        # Filter jobs by level
        if selected_level != "All":
            level_map = {"Intern": "Entry", "Junior": "Entry", "Mid-Level": "Mid", "Senior": "Senior"}
            filtered_jobs = [j for j in jobs if level_map.get(selected_level, '').lower()
                             in (j.get('experience_level') or '').lower()
                             or selected_level.lower() in j.get('title', '').lower()]
            if not filtered_jobs:
                filtered_jobs = jobs  # fallback to all if no match
        else:
            filtered_jobs = jobs

        job_options = ["-- Select a job posting --"] + [
            f"{j['title']} @ {j.get('company_name') or j.get('provider_name','')}"
            for j in filtered_jobs
        ]
        selected_job_label = st.selectbox("Job postings:", job_options, key="gap_job_select")

    with col2:
        st.markdown("**Option B: Type or pick a role**")

        # AI suggested roles as buttons
        cached_roles = st.session_state.get('gap_suggested_roles', [])
        if not cached_roles:
            if st.button("✨ AI Suggest Roles from Resume", use_container_width=True):
                with st.spinner("🤖 Finding best-fit roles..."):
                    parsed = st.session_state.get('resume_parsed', {})
                    raw_titles = parsed.get('job_titles', []) if parsed else []
                    exp_years = parsed.get('experience_years', 0) if parsed else 0
                    roles = suggest_roles_from_resume(
                        seeker_skills, raw_titles, exp_years, selected_level
                    )
                    st.session_state['gap_suggested_roles'] = roles
                    st.rerun()
        else:
            st.markdown(f"**AI Suggestions ({selected_level})** — click to select:")
            # Show as 2-col button grid
            role_cols = st.columns(2)
            active_role = st.session_state.get('gap_selected_suggested_role', '')
            for idx, role in enumerate(cached_roles[:10]):
                with role_cols[idx % 2]:
                    is_active = active_role == role
                    color = LEVEL_COLORS.get(selected_level, '#6366f1')
                    st.markdown(
                        f'<button onclick="" style="width:100%;margin:2px 0;padding:6px 10px;'
                        f'border-radius:6px;border:{"2px solid " + color if is_active else "1px solid #444"};'
                        f'background:{"" + color + "25" if is_active else "transparent"};'
                        f'color:{"" + color if is_active else "#ccc"};cursor:pointer;font-size:0.82em;'
                        f'text-align:left;">{role}</button>',
                        unsafe_allow_html=True
                    )
                    if st.button(role, key=f"gap_role_btn_{idx}", use_container_width=True):
                        st.session_state['gap_selected_suggested_role'] = role
                        st.rerun()

            if st.button("🔄 Refresh Suggestions", use_container_width=True):
                st.session_state.pop('gap_suggested_roles', None)
                st.session_state.pop('gap_selected_suggested_role', None)
                st.rerun()

    custom_role = st.text_input("Or type a custom role:", placeholder="e.g. Computer Vision Engineer",
                                 value=st.session_state.get('gap_selected_suggested_role', ''),
                                 key="gap_custom_role")

    # Resolve final role and skills
    target_role = ""
    req_skills = []
    jd_text = ""

    if selected_job_label != "-- Select a job posting --":
        idx = job_options.index(selected_job_label) - 1
        job = filtered_jobs[idx]
        target_role = job['title']
        jd_text = job['description']
        req_skills = job.get('required_skills', [])
        if isinstance(req_skills, str):
            req_skills = json.loads(req_skills)
    elif custom_role.strip():
        target_role = custom_role.strip()
        jd_text = f"{selected_level} {target_role} role"

    if not target_role:
        st.info("👆 Select a job posting or enter a role name above to continue.")
        return

    st.info(f"🎯 Analyzing gap for: **{target_role}** ({selected_level})")

    if st.button("🔍 Analyze Skill Gap", type="primary", use_container_width=True):
        with st.spinner("🤖 Computing your skill gap..."):
            if not req_skills:
                req_skills = extract_skills_from_jd(jd_text)
            match_result = compute_match_score(seeker_skills, req_skills, jd_text)
            matched = match_result.get('matched_skills', [])
            missing = match_result.get('missing_skills', [])
            score = match_result.get('score', 0)

        with st.spinner("📚 Generating detailed learning plan..."):
            gap_data = analyze_skill_gap(seeker_skills, missing, target_role) if missing else {}

        # Save to DB
        try:
            save_skill_gap(user['id'], target_role, score, matched, missing, gap_data)
        except Exception as e:
            st.warning(f"Could not save to history: {e}")

        st.session_state['gap_result'] = {
            'matched': matched, 'missing': missing,
            'score': score, 'role': target_role, 'gap_data': gap_data
        }
        st.rerun()

    # ── Display results ──
    if 'gap_result' in st.session_state:
        r = st.session_state['gap_result']
        _display_gap_results(user, r['matched'], r['missing'], r['score'],
                             r['role'], r.get('gap_data', {}), seeker_skills)


def _display_gap_results(user, matched, missing, score, role, gap_data, seeker_skills):
    st.markdown("---")

    # Compare with previous analysis for same role
    history = get_latest_two_gaps(user['id'], role)
    prev_score = None
    if len(history) >= 2:
        prev_score = history[1].get('match_score', 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Match Score", f"{score}%",
                delta=f"{round(score - prev_score)}% vs last" if prev_score is not None else None)
    col2.metric("Skills Matched", len(matched))
    col3.metric("Skills Missing", len(missing))
    col4.metric("Gap Closed", f"{round(score - prev_score)}%" if prev_score else "First Analysis",
                delta_color="normal")

    # Skill heatmap
    st.markdown("### 🔥 Skill Gap Heatmap")
    fig = skill_gap_heatmap(matched, missing)
    st.plotly_chart(fig, use_container_width=True)

    # Radar chart
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🕸️ Skill Coverage Radar")
        radar = radar_chart(seeker_skills, SKILL_CATEGORIES)
        st.plotly_chart(radar, use_container_width=True)

    with col2:
        # Matched vs missing donut
        st.markdown("### 🥧 Skill Distribution")
        fig_pie = go.Figure(go.Pie(
            labels=["Matched", "Missing"],
            values=[len(matched), len(missing)],
            hole=0.55,
            marker_colors=["#10b981", "#ef4444"],
            textinfo="label+percent"
        ))
        fig_pie.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

    if not missing:
        st.success("🎉 You have all the required skills for this role!")
        return

    # Improvement roadmap bubble chart
    if gap_data.get('gap_analysis'):
        st.markdown("### 🗺️ Priority Map — Where to Focus")
        fig2 = improvement_roadmap_chart(gap_data['gap_analysis'])
        st.plotly_chart(fig2, use_container_width=True)

    # Ordered learning roadmap
    if gap_data.get('ordered_roadmap'):
        st.markdown("### 📋 Ordered Learning Roadmap")
        st.markdown("*Learn these skills in this exact sequence for maximum efficiency:*")
        for step in gap_data['ordered_roadmap']:
            step_num = step.get('step', 0)
            skill = step.get('skill', '')
            reason = step.get('reason', '')
            milestone = step.get('milestone', '')
            milestone_div = f'<div style="font-size:0.82em;color:#10b981;margin-top:4px;">🎯 {milestone}</div>' if milestone else ''
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;margin:8px 0;'
                f'padding:12px;background:#1e1e2e;border-radius:8px;border-left:3px solid #6366f1;">'
                f'<div style="min-width:36px;height:36px;background:#6366f1;border-radius:50%;'
                f'display:flex;align-items:center;justify-content:center;font-weight:bold;'
                f'color:white;margin-right:14px;">{step_num}</div>'
                f'<div><div style="font-weight:bold;color:#a5b4fc;">{skill}</div>'
                f'<div style="font-size:0.85em;color:#9ca3af;">{reason}</div>'
                f'{milestone_div}'
                f'</div></div>',
                unsafe_allow_html=True
            )

    # Detailed skill cards
    if gap_data.get('gap_analysis'):
        st.markdown("---")
        st.markdown("### 📚 Detailed Skill Breakdown")
        st.markdown("*Click any skill to see why marks were deducted and how to fix it:*")

        progress = get_roadmap_progress(user['id'], role)

        imp_order = {"High": 0, "Medium": 1, "Low": 2}
        sorted_gaps = sorted(gap_data['gap_analysis'],
                             key=lambda x: imp_order.get(x.get('importance', 'Medium'), 1))

        for item in sorted_gaps:
            imp = item.get('importance', 'Medium')
            imp_color = {'High': '#ef4444', 'Medium': '#f59e0b', 'Low': '#3b82f6'}.get(imp, '#6b7280')
            imp_icon = {'High': '🔴', 'Medium': '🟡', 'Low': '🔵'}.get(imp, '⚪')
            skill = item.get('skill', '')
            current_status = progress.get(skill, 'not_started')
            status_icon, status_color, status_label = STATUS_CONFIG[current_status]

            with st.expander(
                f"{imp_icon} **{skill}** — {imp} Priority | ⏱️ {item.get('estimated_time', '')} | {status_icon} {status_label}"
            ):
                col1, col2 = st.columns([3, 1])

                with col1:
                    # Why deducted
                    st.markdown(
                        f'<div style="background:#ef444415;border-left:3px solid #ef4444;'
                        f'padding:10px;border-radius:6px;margin-bottom:10px;">'
                        f'<b style="color:#ef4444;">❌ Why This Hurts Your Profile</b><br>'
                        f'<span style="font-size:0.9em;">{item.get("why_deducted", "")}</span>'
                        f'</div>', unsafe_allow_html=True
                    )
                    # Why needed
                    st.markdown(
                        f'<div style="background:#3b82f615;border-left:3px solid #3b82f6;'
                        f'padding:10px;border-radius:6px;margin-bottom:10px;">'
                        f'<b style="color:#3b82f6;">💡 Why This Matters for {role}</b><br>'
                        f'<span style="font-size:0.9em;">{item.get("why_needed", "")}</span>'
                        f'</div>', unsafe_allow_html=True
                    )
                    # How to improve
                    st.markdown(
                        f'<div style="background:#10b98115;border-left:3px solid #10b981;'
                        f'padding:10px;border-radius:6px;margin-bottom:10px;">'
                        f'<b style="color:#10b981;">🚀 How to Improve</b><br>'
                        f'<span style="font-size:0.9em;">{item.get("how_to_improve", "")}</span>'
                        f'</div>', unsafe_allow_html=True
                    )

                    # Prerequisite
                    prereq = item.get('prerequisite', 'None')
                    if prereq and prereq.lower() != 'none':
                        st.info(f"⚠️ **Learn first:** {prereq}")

                    # Category
                    st.caption(f"📁 Category: {item.get('category', '')}")

                    # Resources
                    resources = item.get('learning_resources', [])
                    if resources:
                        st.markdown("**📖 Resources:**")
                        for res in resources:
                            st.markdown(f"  - 🔗 {res}")

                with col2:
                    st.markdown("**Track Progress:**")
                    for status_key, (s_icon, s_color, s_label) in STATUS_CONFIG.items():
                        is_current = current_status == status_key
                        if st.button(
                            f"{s_icon} {s_label}",
                            key=f"prog_{skill}_{status_key}",
                            use_container_width=True,
                            type="primary" if is_current else "secondary"
                        ):
                            try:
                                upsert_roadmap_progress(user['id'], role, skill, status_key)
                                st.success("Saved!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")


# ─── Tab 2: Upskilling Roadmap ─────────────────────────────────────────────────

def _upskilling_roadmap(user: dict, seeker_skills: list, profile):
    st.markdown("### 🗺️ Personalized Upskilling Roadmap")
    st.markdown("Get a full ordered learning plan with topics, resources, projects, and certifications.")

    # Level filter
    st.markdown("**Target career level:**")
    levels = ["Intern", "Junior", "Mid-Level", "Senior"]
    sel_level = st.session_state.get('roadmap_level', 'Junior')
    lcols = st.columns(4)
    for i, lvl in enumerate(levels):
        with lcols[i]:
            color = LEVEL_COLORS[lvl]
            is_sel = sel_level == lvl
            if st.button(lvl, key=f"rm_lvl_{lvl}", use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                st.session_state['roadmap_level'] = lvl
                st.session_state.pop('roadmap_suggested_roles', None)
                st.rerun()

    sel_level = st.session_state.get('roadmap_level', 'Junior')

    # Role suggestions
    st.markdown("---")
    st.markdown("**Choose your target role:**")
    cached_roles = st.session_state.get('roadmap_suggested_roles', [])

    if not cached_roles:
        if st.button("✨ Suggest Roles from Resume", use_container_width=True):
            with st.spinner("🤖 Analyzing profile..."):
                parsed = st.session_state.get('resume_parsed', {})
                raw_titles = parsed.get('job_titles', []) if parsed else []
                exp_years = parsed.get('experience_years', 0) if parsed else 0
                roles = suggest_roles_from_resume(seeker_skills, raw_titles, exp_years, sel_level)
                st.session_state['roadmap_suggested_roles'] = roles
                st.rerun()
    else:
        st.markdown(f"**Suggested roles for {sel_level} level** — click to select:")
        color = LEVEL_COLORS.get(sel_level, '#6366f1')
        active = st.session_state.get('roadmap_selected_role', '')
        btn_cols = st.columns(3)
        for idx, role in enumerate(cached_roles[:9]):
            with btn_cols[idx % 3]:
                is_active = active == role
                if st.button(
                    ("✅ " if is_active else "") + role,
                    key=f"rm_role_{idx}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary"
                ):
                    st.session_state['roadmap_selected_role'] = role
                    st.rerun()

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔄 Refresh Suggestions", use_container_width=True):
                st.session_state.pop('roadmap_suggested_roles', None)
                st.session_state.pop('roadmap_selected_role', None)
                st.rerun()

    col1, col2 = st.columns([3, 1])
    with col1:
        default_role = st.session_state.get('roadmap_selected_role', '')
        target = st.text_input("Target role:", value=default_role,
                               placeholder="e.g. Senior Data Scientist")
    with col2:
        exp = st.number_input("Years of experience:", min_value=0, max_value=30, value=2)

    if st.button("📈 Generate Full Roadmap", type="primary", use_container_width=True):
        if not target:
            st.warning("Please enter a target role.")
            return
        with st.spinner("🤖 Building your personalized roadmap..."):
            roadmap = get_upskilling_recommendations(seeker_skills, target, exp)
        st.session_state['roadmap'] = roadmap
        st.session_state['roadmap_target'] = target

    if 'roadmap' in st.session_state:
        _display_roadmap(user, st.session_state['roadmap'],
                         st.session_state.get('roadmap_target', target))


def _display_roadmap(user: dict, r: dict, target_role: str):
    st.markdown("---")

    # Ordered roadmap as visual steps
    if r.get('ordered_roadmap'):
        st.markdown("### 🗺️ Your Learning Path — In Order")
        st.markdown("*Follow these steps sequentially for the most efficient progress:*")

        progress = get_roadmap_progress(user['id'], target_role)
        steps = r['ordered_roadmap']
        total_steps = len(steps)
        completed = sum(1 for s in steps if progress.get(s.get('skill', ''), '') == 'completed')

        # Progress bar
        pct = completed / total_steps if total_steps else 0
        st.progress(pct)
        st.caption(f"{completed}/{total_steps} skills completed")

        for step in steps:
            skill = step.get('skill', '')
            current_status = progress.get(skill, 'not_started')
            s_icon, s_color, s_label = STATUS_CONFIG[current_status]
            timeframe = step.get('timeframe', '')
            depends = step.get('depends_on', '')
            why_order = step.get('why_this_order', '')

            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(
                    f'<div style="display:flex;align-items:center;margin:6px 0;'
                    f'padding:12px 16px;background:{"#10b98115" if current_status == "completed" else "#1a1a2e"};'
                    f'border-radius:8px;border-left:3px solid {s_color};">'
                    f'<span style="font-size:1.4em;margin-right:12px;">{s_icon}</span>'
                    f'<div>'
                    f'<b style="color:{"#10b981" if current_status == "completed" else "#e2e8f0"};">'
                    f'Step {step.get("step","")}: {skill}</b>'
                    f'<span style="color:#6b7280;font-size:0.8em;margin-left:8px;">⏱️ {timeframe}</span><br>'
                    f'<span style="color:#9ca3af;font-size:0.82em;">{why_order}</span>'
                    + (f'<br><span style="color:#6b7280;font-size:0.78em;">↩ After: {depends}</span>' if depends and depends.lower() != 'start here' else '')
                    + f'</div></div>',
                    unsafe_allow_html=True
                )
            with col2:
                next_status = {
                    'not_started': 'in_progress',
                    'in_progress': 'completed',
                    'completed': 'not_started'
                }[current_status]
                btn_labels = {
                    'not_started': '▶️ Start',
                    'in_progress': '✅ Done',
                    'completed': '🔄 Redo'
                }
                if st.button(btn_labels[current_status], key=f"rm_prog_{skill}",
                             use_container_width=True):
                    try:
                        upsert_roadmap_progress(user['id'], target_role, skill, next_status)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    st.markdown("---")

    # Detailed skill sections by timeframe
    for section, label, icon, color in [
        ('short_term',  '1–3 Months',  '🌱', '#10b981'),
        ('medium_term', '3–6 Months',  '🌿', '#3b82f6'),
        ('long_term',   '6–12 Months', '🌳', '#f59e0b')
    ]:
        items = r.get(section, [])
        if not items:
            continue
        st.markdown(f"### {icon} {label}")
        for item in items:
            skill = item.get('skill', '')
            with st.expander(f"**{skill}** — {item.get('why', '')[:60]}..."):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Why learn this:** {item.get('why', '')}")
                    st.markdown(f"**After learning you can:** {item.get('what_you_can_do_after', '')}")
                    st.markdown(f"**Resource:** 🔗 {item.get('resource', '')}")

                    # Sub-topics in order
                    topics = item.get('topics', [])
                    if topics:
                        st.markdown("**📋 Topics to study (in order):**")
                        for t_idx, topic in enumerate(topics):
                            st.markdown(
                                f'<div style="margin:4px 0;padding:6px 12px;'
                                f'background:#1e1e2e;border-radius:6px;border-left:2px solid {color};">'
                                f'<span style="color:{color};font-weight:bold;">{t_idx+1}.</span> {topic}'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                with col2:
                    progress = get_roadmap_progress(user['id'], target_role)
                    current_status = progress.get(skill, 'not_started')
                    s_icon, s_color, s_label = STATUS_CONFIG[current_status]
                    st.markdown(f"**Status:** {s_icon} {s_label}")
                    next_status = {'not_started': 'in_progress', 'in_progress': 'completed', 'completed': 'not_started'}[current_status]
                    if st.button({'not_started': '▶️ Start', 'in_progress': '✅ Mark Done', 'completed': '🔄 Reset'}[current_status],
                                 key=f"rm2_prog_{skill}", use_container_width=True):
                        try:
                            upsert_roadmap_progress(user['id'], target_role, skill, next_status)
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

    # Certifications
    certs = r.get('certifications', [])
    if certs:
        st.markdown("### 🏆 Recommended Certifications")
        for cert in certs:
            if isinstance(cert, dict):
                st.markdown(
                    f'<div style="padding:12px;background:#1e1e2e;border-radius:8px;'
                    f'margin:6px 0;border-left:3px solid #f59e0b;">'
                    f'🎓 <b>{cert.get("name","")}</b> — {cert.get("provider","")}<br>'
                    f'<span style="color:#9ca3af;font-size:0.85em;">{cert.get("why_useful","")}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(f"🎓 {cert}")

    # Projects
    projects = r.get('projects', [])
    if projects:
        st.markdown("### 🛠️ Portfolio Projects to Build")
        for proj in projects:
            if isinstance(proj, dict):
                diff_color = {'Easy': '#10b981', 'Medium': '#f59e0b', 'Hard': '#ef4444'}.get(proj.get('difficulty',''), '#6b7280')
                with st.expander(f"💡 **{proj.get('name','')}** — Difficulty: {proj.get('difficulty','')}"):
                    st.markdown(f"**Description:** {proj.get('description','')}")
                    skills_prac = proj.get('skills_practiced', [])
                    if skills_prac:
                        st.markdown(f"**Skills practiced:** {', '.join(skills_prac)}")
            else:
                st.markdown(f"💡 {proj}")


# ─── Tab 3: Progress History ───────────────────────────────────────────────────

def _progress_history(user: dict):
    st.markdown("### 📈 Your Skill Gap Progress Over Time")

    history = get_skill_gap_history(user['id'], limit=20)

    if not history:
        st.info("No history yet. Run a Skill Gap Analysis to start tracking your progress!")
        return

    # Group by role
    roles = list(dict.fromkeys([h['target_role'] for h in history]))

    selected_role = st.selectbox("Filter by role:", ["All Roles"] + roles)
    filtered = [h for h in history if selected_role == "All Roles" or h['target_role'] == selected_role]

    # Score over time chart
    df = pd.DataFrame([{
        'Date': str(h['created_at'])[:10],
        'Role': h['target_role'],
        'Match Score': round(h['match_score'] or 0),
        'Missing Skills': len(json.loads(h['missing_skills']) if isinstance(h['missing_skills'], str) else h.get('missing_skills', []))
    } for h in filtered])

    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Match Score Over Time**")
            fig = px.line(df, x='Date', y='Match Score', color='Role',
                          markers=True, color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(height=280, paper_bgcolor='rgba(0,0,0,0)',
                               plot_bgcolor='rgba(248,248,248,0.05)',
                               yaxis=dict(range=[0, 100]))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("**Missing Skills Count Over Time**")
            fig2 = px.bar(df, x='Date', y='Missing Skills', color='Role',
                          color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_layout(height=280, paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(248,248,248,0.05)')
            st.plotly_chart(fig2, use_container_width=True)

    # Latest vs previous comparison
    if selected_role != "All Roles" and len(filtered) >= 2:
        st.markdown("---")
        st.markdown("### 🔄 Latest vs Previous Analysis")
        latest = filtered[0]
        prev = filtered[1]

        latest_missing = json.loads(latest['missing_skills']) if isinstance(latest['missing_skills'], str) else (latest.get('missing_skills') or [])
        prev_missing = json.loads(prev['missing_skills']) if isinstance(prev['missing_skills'], str) else (prev.get('missing_skills') or [])

        newly_gained = [s for s in prev_missing if s not in latest_missing]
        still_missing = [s for s in latest_missing if s in prev_missing]
        newly_missing = [s for s in latest_missing if s not in prev_missing]

        c1, c2, c3 = st.columns(3)
        c1.metric("Score Change", f"{round(latest['match_score'] or 0)}%",
                  delta=f"{round((latest['match_score'] or 0) - (prev['match_score'] or 0))}%")
        c2.metric("Skills Gained", len(newly_gained), delta=f"+{len(newly_gained)}")
        c3.metric("Still Missing", len(still_missing))

        if newly_gained:
            st.success(f"✅ **Skills you've gained since last analysis:** {', '.join(newly_gained)}")
        if still_missing:
            st.warning(f"⚠️ **Still missing:** {', '.join(still_missing[:8])}")

    # Full history table
    st.markdown("---")
    st.markdown("### 📋 Full History")
    display_df = df[['Date', 'Role', 'Match Score', 'Missing Skills']].copy()
    st.dataframe(display_df, use_container_width=True, hide_index=True)
