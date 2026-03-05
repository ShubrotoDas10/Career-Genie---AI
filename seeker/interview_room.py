import streamlit as st
import json
from shared.db import (
    get_job_by_id, get_interview_by_application, create_interview,
    save_interview_results, get_seeker_profile, get_applications_by_seeker,
)
from shared.groq_client import (
    generate_leveled_questions, evaluate_answer, generate_level_feedback,
    generate_interview_summary, suggest_roles_from_resume, LEVEL_CONFIG
)
from shared.analytics import interview_scorecard


# ─── Entry Point ──────────────────────────────────────────────────────────────

def show_interview_room(user: dict):
    st.markdown("## 🎤 AI Mock Interview Room")
    st.markdown("---")

    if st.session_state.get('interview_active'):
        _run_level_interview(user)
        return

    if st.session_state.get('interview_all_done'):
        _show_final_results(user)
        return

    _show_setup_screen(user)


# ─── Setup Screen ─────────────────────────────────────────────────────────────

def _show_setup_screen(user: dict):
    profile = get_seeker_profile(user['id'])
    seeker_skills = []

    if profile:
        raw = profile.get('extracted_skills', [])
        seeker_skills = json.loads(raw) if isinstance(raw, str) else (raw or [])

    tab1, tab2 = st.tabs(["📋 Interview for Applied Job", "🧪 Practice / Dummy Interview"])

    with tab1:
        _applied_job_tab(user, seeker_skills)

    with tab2:
        _dummy_interview_tab(user, seeker_skills, profile)


# ─── Tab 1: Applied Job ────────────────────────────────────────────────────────

def _applied_job_tab(user: dict, seeker_skills: list):
    apps = get_applications_by_seeker(user['id'])

    if not apps:
        st.info("You haven't applied to any jobs yet. Browse jobs and apply to unlock this tab.")
        if st.button("🔍 Browse Jobs", type="primary"):
            st.session_state['seeker_page'] = 'jobs'
            st.rerun()
        return

    st.markdown("### Select an Applied Job to Interview For")

    options = {}
    for app in apps:
        label = (f"{app['title']}  @  {app.get('company_name') or app.get('provider_name', 'Company')}"
                 f"  |  Match: {round(app.get('match_score', 0))}%"
                 f"  |  {app.get('status','applied').capitalize()}")
        options[label] = app

    selected_label = st.selectbox("Choose a job:", list(options.keys()))
    selected_app = options[selected_label]
    job = get_job_by_id(selected_app['job_id'])

    if not job:
        st.error("Job data not found.")
        return

    config = job.get('interview_config', {})
    if isinstance(config, str):
        config = json.loads(config)
    tech_stack = job.get('tech_stack', [])
    if isinstance(tech_stack, str):
        tech_stack = json.loads(tech_stack)
    req_skills = job.get('required_skills', [])
    if isinstance(req_skills, str):
        req_skills = json.loads(req_skills)

    matched = [s for s in seeker_skills if any(s.lower() in r.lower() or r.lower() in s.lower() for r in req_skills)]
    missing = [r for r in req_skills if not any(r.lower() in s.lower() or s.lower() in r.lower() for s in seeker_skills)]

    col1, col2, col3 = st.columns(3)
    col1.metric("Your Match", f"{round(selected_app.get('match_score', 0))}%")
    col2.metric("Skills Matched", len(matched))
    col3.metric("Stretch Skills", len(missing))

    if missing:
        st.markdown(f"**Stretch skills included:** {', '.join(missing[:6])}")
    if tech_stack:
        st.markdown(f"**Tech stack focus:** {', '.join(tech_stack)}")

    _show_level_selector_and_start(
        user=user, role=job['title'],
        seeker_skills=seeker_skills, missing_skills=missing,
        tech_stack=tech_stack, job_id=job['id'],
        app_id=selected_app['id'], mode="applied"
    )


# ─── Tab 2: Practice Interview ─────────────────────────────────────────────────

def _dummy_interview_tab(user: dict, seeker_skills: list, profile):
    st.markdown("### 🧪 Practice Interview — No Application Required")
    st.markdown("Configure your session and AI will tailor questions to your skills + growth areas.")

    # Step 1: Role selection
    st.markdown("#### Step 1: Choose Your Target Role")

    if seeker_skills:
        if st.button("✨ Suggest Roles Based on My Resume", use_container_width=True):
            with st.spinner("🤖 Analyzing your profile for best-fit roles..."):
                parsed = st.session_state.get('resume_parsed', {})
                raw_titles = parsed.get('job_titles', []) if parsed else []
                exp_years = parsed.get('experience_years', 0) if parsed else 0
                roles = suggest_roles_from_resume(seeker_skills, raw_titles, exp_years)
                st.session_state['suggested_roles'] = roles
    else:
        st.info("Upload your resume first to get AI role suggestions.")

    cached_roles = st.session_state.get('suggested_roles', [])
    custom_role = ""

    if cached_roles:
        st.markdown("**AI Suggested Roles:**")
        role_pick = st.selectbox(
            "Pick a suggested role or type your own:",
            ["-- Type my own --"] + cached_roles,
            key="role_sugg_select"
        )
        if role_pick != "-- Type my own --":
            custom_role = role_pick
        else:
            custom_role = st.text_input("Your target role:", placeholder="e.g. Machine Learning Engineer")
    else:
        common_roles = [
            "", "Software Engineer", "Data Scientist", "Frontend Developer",
            "Backend Developer", "Full Stack Developer", "DevOps Engineer",
            "Data Analyst", "Machine Learning Engineer", "Product Manager",
            "Cloud Architect", "Mobile Developer", "Cybersecurity Analyst"
        ]
        col1, col2 = st.columns([2, 1])
        with col1:
            custom_role = st.text_input("Type your target role:", placeholder="e.g. Senior Data Scientist")
        with col2:
            quick = st.selectbox("Or pick common role:", common_roles)
            if quick:
                custom_role = quick

    role = custom_role.strip() if custom_role else ""
    st.markdown("---")

    # Step 2: Tech stack
    st.markdown("#### Step 2: Tech Stack Focus")
    default_tech = ", ".join(seeker_skills[:5]) if seeker_skills else ""
    tech_input = st.text_input(
        "Key technologies (comma-separated):",
        value=default_tech,
        placeholder="e.g. Python, FastAPI, PostgreSQL, Docker"
    )
    tech_stack = [t.strip() for t in tech_input.split(',') if t.strip()]

    st.markdown("---")

    # Step 3: Stretch skills
    st.markdown("#### Step 3: Skills You Want to Improve")
    stretch_input = st.text_input(
        "Skills you're weak on / want to practice (comma-separated):",
        placeholder="e.g. System Design, Kubernetes, GraphQL"
    )
    missing_skills = [s.strip() for s in stretch_input.split(',') if s.strip()]
    if not missing_skills:
        st.caption("💡 Leave blank — AI will pick stretch topics based on your role and level.")

    st.markdown("---")

    if not role:
        st.warning("Please enter or select a target role to continue.")
        return

    _show_level_selector_and_start(
        user=user, role=role,
        seeker_skills=seeker_skills, missing_skills=missing_skills,
        tech_stack=tech_stack, job_id=None, app_id=None, mode="practice"
    )


# ─── Level Selector ────────────────────────────────────────────────────────────

def _show_level_selector_and_start(user, role, seeker_skills, missing_skills,
                                    tech_stack, job_id, app_id, mode):
    st.markdown("---")
    st.markdown("#### 🎯 Choose Your Starting Level")

    level_meta = {
        1: ("🌱", "Foundations",      "Core concepts, definitions",            "#10b981"),
        2: ("🌿", "Practical",        "Real-world patterns & tool usage",       "#3b82f6"),
        3: ("⚙️", "Problem Solving",  "Debugging, use-cases, trade-offs",       "#f59e0b"),
        4: ("🔥", "Advanced",         "Architecture, hard coding, edge cases",  "#ef4444"),
        5: ("💎", "Expert",           "System design, leadership, expert code", "#8b5cf6"),
    }

    selected_level = st.session_state.get(f'selected_start_level_{mode}', 1)
    cols = st.columns(5)

    for i, (lvl, (icon, label, desc, color)) in enumerate(level_meta.items()):
        with cols[i]:
            is_sel = selected_level == lvl
            border = f"3px solid {color}" if is_sel else "1px solid #e5e7eb"
            bg = color + "18" if is_sel else "transparent"
            st.markdown(
                f'<div style="border:{border};border-radius:10px;padding:12px;'
                f'text-align:center;background:{bg};">'
                f'<div style="font-size:1.6em;">{icon}</div>'
                f'<div style="font-weight:bold;color:{color};">L{lvl}</div>'
                f'<div style="font-size:0.82em;font-weight:600;">{label}</div>'
                f'<div style="font-size:0.72em;color:#999;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button(f"Pick L{lvl}", key=f"pick_{lvl}_{mode}", use_container_width=True):
                st.session_state[f'selected_start_level_{mode}'] = lvl
                st.rerun()

    selected_level = st.session_state.get(f'selected_start_level_{mode}', 1)
    cfg = LEVEL_CONFIG[selected_level]

    type_icons = {
        "conceptual": "📖", "behavioral": "💬", "technical": "⚙️",
        "scenario": "🎭", "debugging": "🐛", "use_case": "💡",
        "coding": "💻", "architecture": "🏗️", "system_design": "🌐", "leadership": "👥"
    }
    types_str = "  ".join([f"{type_icons.get(t,'❓')} `{t}`" for t in cfg['question_types']])

    st.info(
        f"**Level {selected_level}: {cfg['label']}** — {cfg['description']}  |  "
        f"Difficulty: `{cfg['difficulty']}`  |  "
        f"{cfg['count']} questions × {cfg['marks']} marks = **{cfg['count'] * cfg['marks']} marks**"
    )
    st.markdown(f"Question types: {types_str}")
    st.markdown("")

    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button(f"🚀 Start Level {selected_level} Interview for **{role}**",
                     type="primary", use_container_width=True):
            with st.spinner(f"🤖 Generating Level {selected_level} questions for {role}..."):
                questions = generate_leveled_questions(
                    role=role, skills=seeker_skills,
                    missing_skills=missing_skills, level=selected_level
                )
            if not questions:
                st.error("Failed to generate questions. Please try again.")
                return

            st.session_state.update({
                'interview_active': True,
                'interview_all_done': False,
                'interview_role': role,
                'interview_mode': mode,
                'interview_job_id': job_id,
                'interview_app_id': app_id,
                'interview_tech_stack': tech_stack,
                'interview_seeker_skills': seeker_skills,
                'interview_missing_skills': missing_skills,
                'current_level': selected_level,
                'current_level_questions': questions,
                'current_level_answers': {},
                'current_question_idx': 0,
                'level_results': {},
                'interview_max_score': sum(q.get('marks', cfg['marks']) for q in questions),
            })
            st.rerun()
    with col2:
        st.caption("All 5 levels available. Each unlocks after completing the previous one.")


# ─── Active Interview ──────────────────────────────────────────────────────────

def _run_level_interview(user: dict):
    level = st.session_state.get('current_level', 1)
    questions = st.session_state.get('current_level_questions', [])
    answers = st.session_state.get('current_level_answers', {})
    idx = st.session_state.get('current_question_idx', 0)
    role = st.session_state.get('interview_role', 'the role')
    cfg = LEVEL_CONFIG[level]

    level_colors = {1:"#10b981", 2:"#3b82f6", 3:"#f59e0b", 4:"#ef4444", 5:"#8b5cf6"}
    color = level_colors.get(level, "#6366f1")

    st.markdown(
        f'<div style="background:{color}15;border:1px solid {color}40;border-radius:10px;'
        f'padding:12px 20px;margin-bottom:14px;">'
        f'<b style="color:{color};">Level {level}: {cfg["label"]}</b>'
        f'<span style="color:#888;margin-left:12px;">— {role}</span>'
        f'<span style="float:right;color:{color};">{cfg["difficulty"]}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    st.progress(idx / len(questions) if questions else 0)
    st.caption(f"Question {min(idx + 1, len(questions))} of {len(questions)}")

    if idx >= len(questions):
        _evaluate_level(user, level, questions, answers, role)
        return

    _render_question(questions[idx], idx, len(questions), answers, level)


def _render_question(question: dict, idx: int, total: int, answers: dict, level: int):
    q_type = question.get('type', 'technical')
    type_cfg = {
        'conceptual':   ('📖', '#6366f1', 'Explain clearly with examples.'),
        'behavioral':   ('💬', '#8b5cf6', 'Use STAR: Situation, Task, Action, Result.'),
        'technical':    ('⚙️', '#f59e0b', 'Be specific with implementation details.'),
        'scenario':     ('🎭', '#3b82f6', 'Walk through your thought process.'),
        'debugging':    ('🐛', '#ef4444', 'Find the bug, fix it, explain why it happened.'),
        'use_case':     ('💡', '#10b981', 'Explain when, why, and trade-offs.'),
        'coding':       ('💻', '#10b981', 'Write clean code. Explain your approach + complexity.'),
        'architecture': ('🏗️', '#f59e0b', 'Think scalability, maintainability, trade-offs.'),
        'system_design':('🌐', '#6366f1', 'Cover components, data flow, scaling, failures.'),
        'leadership':   ('👥', '#8b5cf6', 'Focus on outcomes, dynamics, lessons learned.'),
    }
    icon, color, placeholder = type_cfg.get(q_type, ('❓', '#6b7280', 'Answer thoroughly.'))
    stretch = question.get('is_stretch', False)

    st.markdown(
        f'<div style="background:{color}10;border-left:4px solid {color};'
        f'padding:18px;border-radius:8px;margin-bottom:14px;">'
        f'<div style="margin-bottom:10px;">'
        f'<span style="color:{color};font-weight:bold;">{icon} {q_type.replace("_"," ").title()}</span>'
        + (f' <span style="background:#f59e0b20;color:#f59e0b;font-size:0.75em;'
           f'padding:2px 8px;border-radius:10px;">🌱 Stretch Skill</span>' if stretch else '') +
        f'<span style="float:right;color:#888;">{question.get("marks", 10)} marks</span>'
        f'</div>'
        f'<div style="font-size:1.05em;line-height:1.7;white-space:pre-wrap;">{question["question"]}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    if question.get('hint'):
        with st.expander("💡 Hint"):
            st.info(question['hint'])

    answer = st.text_area(
        "Your Answer:",
        value=answers.get(idx, ""),
        height=230,
        placeholder=placeholder,
        key=f"ans_{level}_{idx}"
    )

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("⬅️ Previous", disabled=(idx == 0), use_container_width=True):
            answers[idx] = answer
            st.session_state['current_level_answers'] = answers
            st.session_state['current_question_idx'] = idx - 1
            st.rerun()
    with col2:
        if st.button("⏭️ Skip", use_container_width=True):
            answers[idx] = answer or "(skipped)"
            st.session_state['current_level_answers'] = answers
            st.session_state['current_question_idx'] = idx + 1
            st.rerun()
    with col3:
        label = "Next ➡️" if idx < total - 1 else "✅ Submit Level"
        if st.button(label, type="primary", disabled=not answer.strip(), use_container_width=True):
            answers[idx] = answer
            st.session_state['current_level_answers'] = answers
            st.session_state['current_question_idx'] = idx + 1
            st.rerun()


# ─── Level Evaluation ─────────────────────────────────────────────────────────

def _evaluate_level(user, level, questions, answers, role):
    cfg = LEVEL_CONFIG[level]
    tech_stack = st.session_state.get('interview_tech_stack', [])

    st.markdown(f"### ⏳ Evaluating Level {level}: {cfg['label']}...")
    scores = []
    bar = st.progress(0)
    status = st.empty()

    for i, q in enumerate(questions):
        status.text(f"Evaluating Q{i+1}/{len(questions)}...")
        score = evaluate_answer(
            question=q['question'], q_type=q.get('type', 'technical'),
            answer=answers.get(i, ""),
            max_marks=q.get('marks', cfg['marks']),
            expected_keywords=q.get('expected_keywords', []),
            tech_stack=tech_stack
        )
        scores.append(score)
        bar.progress((i + 1) / len(questions))

    status.text("Generating level feedback...")
    fb = generate_level_feedback(role, level, questions, list(answers.values()), scores)
    bar.empty(); status.empty()

    # Store
    level_results = st.session_state.get('level_results', {})
    level_results[level] = {'questions': questions, 'answers': answers, 'scores': scores, 'feedback': fb}
    st.session_state['level_results'] = level_results

    total = sum(s.get('score', 0) for s in scores)
    max_total = sum(q.get('marks', cfg['marks']) for q in questions)
    pct = round(total / max_total * 100) if max_total else 0
    passed = fb.get('ready_for_next', pct >= 60)

    level_colors = {1:"#10b981", 2:"#3b82f6", 3:"#f59e0b", 4:"#ef4444", 5:"#8b5cf6"}
    color = level_colors.get(level, "#6366f1")

    st.markdown(f"## 📊 Level {level} Results: {cfg['label']}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Score", f"{total}/{max_total}")
    c2.metric("Percentage", f"{pct}%")
    c3.metric("Ready for Next?", "✅ Yes" if passed else "⚠️ Review first")

    st.markdown(f"**{fb.get('summary','')}**")
    st.info(f"💪 {fb.get('encouragement','Keep going!')}")

    col1, col2 = st.columns(2)
    with col1:
        if fb.get('strong_areas'):
            st.markdown("**✅ Strong Areas:**")
            for s in fb['strong_areas']:
                st.markdown(f"- {s}")
    with col2:
        if fb.get('weak_areas'):
            st.markdown("**💡 Revisit Before Next Level:**")
            for w in fb['weak_areas']:
                st.markdown(f"- {w}")

    with st.expander("📋 Question Breakdown"):
        for i, (q, s) in enumerate(zip(questions, scores)):
            q_pct = round(s.get('score',0) / q.get('marks', cfg['marks']) * 100) if q.get('marks') else 0
            dot = '🟢' if q_pct >= 70 else '🟡' if q_pct >= 40 else '🔴'
            stretch = " 🌱" if q.get('is_stretch') else ""
            st.markdown(f"{dot} **Q{i+1}** `{q.get('type','').replace('_',' ').title()}`{stretch}"
                        f" — `{s.get('score',0)}/{q.get('marks',cfg['marks'])}`")
            st.markdown(f"  _{s.get('feedback','')[:150]}_")

    st.markdown("---")

    if level < 5:
        c1, c2, c3 = st.columns(3)
        with c1:
            lbl = f"➡️ Level {level+1}: {LEVEL_CONFIG[level+1]['label']}" if passed else f"⚠️ Try Level {level+1} Anyway"
            if st.button(lbl, type="primary", use_container_width=True):
                _start_next_level(level + 1)
        with c2:
            if st.button(f"🔄 Retry Level {level}", use_container_width=True):
                _start_next_level(level)
        with c3:
            if st.button("🏁 Finish & Full Report", use_container_width=True):
                st.session_state['interview_active'] = False
                st.session_state['interview_all_done'] = True
                st.rerun()
    else:
        if st.button("🏆 See Full Interview Report", type="primary", use_container_width=True):
            st.session_state['interview_active'] = False
            st.session_state['interview_all_done'] = True
            st.rerun()


def _start_next_level(level: int):
    role = st.session_state.get('interview_role', '')
    seeker_skills = st.session_state.get('interview_seeker_skills', [])
    missing_skills = st.session_state.get('interview_missing_skills', [])
    cfg = LEVEL_CONFIG[level]

    with st.spinner(f"🤖 Generating Level {level}: {cfg['label']} questions..."):
        questions = generate_leveled_questions(role=role, skills=seeker_skills,
                                               missing_skills=missing_skills, level=level)
    if not questions:
        st.error("Failed to generate questions. Try again.")
        return

    st.session_state.update({
        'current_level': level,
        'current_level_questions': questions,
        'current_level_answers': {},
        'current_question_idx': 0,
        'interview_active': True,
    })
    st.rerun()


# ─── Final Report ──────────────────────────────────────────────────────────────

def _show_final_results(user: dict):
    level_results = st.session_state.get('level_results', {})
    role = st.session_state.get('interview_role', 'the role')

    if not level_results:
        st.info("No results to show.")
        return

    st.markdown(f"## 🏆 Full Interview Report — {role}")
    st.markdown("---")

    all_q, all_s, total_earned, total_max = [], [], 0, 0
    for lvl in sorted(level_results.keys()):
        r = level_results[lvl]
        all_q.extend(r['questions'])
        all_s.extend(r['scores'])
        total_earned += sum(s.get('score', 0) for s in r['scores'])
        total_max += sum(q.get('marks', 10) for q in r['questions'])

    pct = round(total_earned / total_max * 100) if total_max else 0
    levels_done = len(level_results)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Levels Done", f"{levels_done}/5")
    c2.metric("Total Score", f"{total_earned}/{total_max}")
    c3.metric("Overall %", f"{pct}%")
    c4.metric("Grade", _grade(pct))

    # Level summary row
    level_colors = {1:"#10b981", 2:"#3b82f6", 3:"#f59e0b", 4:"#ef4444", 5:"#8b5cf6"}
    st.markdown("### 📊 Performance by Level")
    lcols = st.columns(levels_done)
    for i, lvl in enumerate(sorted(level_results.keys())):
        r = level_results[lvl]
        earned = sum(s.get('score',0) for s in r['scores'])
        mx = sum(q.get('marks',10) for q in r['questions'])
        lvl_pct = round(earned/mx*100) if mx else 0
        color = level_colors[lvl]
        with lcols[i]:
            st.markdown(
                f'<div style="border:1px solid {color}50;border-radius:8px;padding:10px;text-align:center;">'
                f'<div style="color:{color};font-weight:bold;font-size:0.85em;">L{lvl}: {LEVEL_CONFIG[lvl]["label"]}</div>'
                f'<div style="font-size:1.6em;font-weight:bold;">{lvl_pct}%</div>'
                f'<div style="font-size:0.78em;color:#888;">{earned}/{mx}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    if all_q and all_s:
        st.markdown("### 📈 Full Score Chart")
        fig = interview_scorecard(all_q, all_s)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🤖 AI Overall Assessment")
    with st.spinner("Generating final assessment..."):
        all_answers = []
        for lvl in sorted(level_results.keys()):
            r = level_results[lvl]
            all_answers.extend([r['answers'].get(i, '') for i in range(len(r['questions']))])
        summary = generate_interview_summary(role, all_q, all_answers, all_s, total_earned, total_max)
    st.markdown(summary)

    st.markdown("---")
    st.markdown("### 🔍 Level-by-Level Deep Dive")
    for lvl in sorted(level_results.keys()):
        r = level_results[lvl]
        cfg = LEVEL_CONFIG[lvl]
        fb = r.get('feedback', {})
        earned = sum(s.get('score',0) for s in r['scores'])
        mx = sum(q.get('marks',10) for q in r['questions'])
        lvl_pct = round(earned/mx*100) if mx else 0
        color = level_colors[lvl]

        with st.expander(f"Level {lvl}: {cfg['label']} — {lvl_pct}% ({earned}/{mx})"):
            if fb.get('strong_areas'):
                st.markdown("**✅ Strong:** " + ", ".join(fb['strong_areas']))
            if fb.get('weak_areas'):
                st.markdown("**💡 Improve:** " + ", ".join(fb['weak_areas']))
            st.markdown(f"_{fb.get('summary','')}_")
            st.markdown("")
            for i, (q, s) in enumerate(zip(r['questions'], r['scores'])):
                q_pct = round(s.get('score',0) / q.get('marks', cfg['marks']) * 100) if q.get('marks') else 0
                dot = '🟢' if q_pct >= 70 else '🟡' if q_pct >= 40 else '🔴'
                stretch = " 🌱" if q.get('is_stretch') else ""
                st.markdown(f"{dot} **Q{i+1}** `{q.get('type','').replace('_',' ').title()}`{stretch}: "
                            f"`{s.get('score',0)}/{q.get('marks',cfg['marks'])}`")
                if s.get('feedback'):
                    st.markdown(f"  _{s['feedback'][:180]}_")
                if s.get('improvements'):
                    for imp in s['improvements'][:2]:
                        st.markdown(f"  → {imp}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Start New Interview", type="primary", use_container_width=True):
            for key in ['interview_active', 'interview_all_done', 'level_results',
                        'current_level', 'current_level_questions', 'current_level_answers',
                        'current_question_idx', 'interview_role', 'suggested_roles',
                        'selected_start_level_applied', 'selected_start_level_practice']:
                st.session_state.pop(key, None)
            st.rerun()
    with c2:
        if st.button("📊 Skill Gap Analysis", use_container_width=True):
            st.session_state['seeker_page'] = 'gap'
            st.rerun()


def _grade(pct: int) -> str:
    if pct >= 90: return "🏆 A+"
    if pct >= 80: return "⭐ A"
    if pct >= 70: return "✅ B"
    if pct >= 60: return "🟡 C"
    if pct >= 50: return "⚠️ D"
    return "❌ F"
