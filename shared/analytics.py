import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json


def radar_chart(skills_present: list, all_categories: dict) -> go.Figure:
    """
    Radar chart showing skill coverage across domains.
    all_categories: {"Backend": ["Python","Node"], "Frontend": ["React"], ...}
    """
    categories = list(all_categories.keys())
    scores = []
    for cat, skills in all_categories.items():
        if not skills:
            scores.append(0)
            continue
        matched = sum(1 for s in skills if any(s.lower() in sp.lower() or sp.lower() in s.lower()
                                                for sp in skills_present))
        scores.append(round(matched / len(skills) * 100))

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores + [scores[0]],
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(99, 102, 241, 0.2)',
        line=dict(color='rgb(99, 102, 241)', width=2),
        name='Your Skills'
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100],
                            tickfont=dict(size=10), gridcolor='rgba(0,0,0,0.1)'),
            angularaxis=dict(tickfont=dict(size=12))
        ),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=60, r=60, t=40, b=40),
        height=380
    )
    return fig


def skill_gap_heatmap(matched_skills: list, missing_skills: list) -> go.Figure:
    """Heatmap showing present vs missing skills."""
    all_skills = matched_skills + missing_skills
    if not all_skills:
        return go.Figure()

    values = [1] * len(matched_skills) + [0] * len(missing_skills)
    colors = ['#10b981'] * len(matched_skills) + ['#ef4444'] * len(missing_skills)
    labels = ['✅ Present'] * len(matched_skills) + ['❌ Missing'] * len(missing_skills)

    fig = go.Figure(go.Bar(
        x=all_skills,
        y=[1] * len(all_skills),
        marker_color=colors,
        text=labels,
        textposition='inside',
        hovertemplate='<b>%{x}</b><br>%{text}<extra></extra>'
    ))
    fig.update_layout(
        title="Skill Gap Overview",
        yaxis=dict(visible=False),
        xaxis=dict(tickangle=-35),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(248,248,248,0.8)',
        height=350,
        margin=dict(l=20, r=20, t=50, b=100),
        bargap=0.15
    )
    return fig


def interview_scorecard(questions: list, scores: list) -> go.Figure:
    """Bar chart showing score per interview question."""
    if not questions or not scores:
        return go.Figure()

    labels = [f"Q{i+1} ({q.get('type','')[:4]})" for i, q in enumerate(questions)]
    earned = [s.get('score', 0) for s in scores]
    max_marks = [q.get('marks', 10) for q in questions]
    pct = [round(e/m*100) if m else 0 for e, m in zip(earned, max_marks)]
    colors = ['#10b981' if p >= 70 else '#f59e0b' if p >= 40 else '#ef4444' for p in pct]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Max Marks',
        x=labels, y=max_marks,
        marker_color='rgba(229,231,235,0.8)',
        hovertemplate='%{x}<br>Max: %{y}<extra></extra>'
    ))
    fig.add_trace(go.Bar(
        name='Your Score',
        x=labels, y=earned,
        marker_color=colors,
        text=[f"{p}%" for p in pct],
        textposition='outside',
        hovertemplate='%{x}<br>Score: %{y} (%{text})<extra></extra>'
    ))
    fig.update_layout(
        barmode='overlay',
        title="Interview Performance by Question",
        xaxis_title="Questions",
        yaxis_title="Marks",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(248,248,248,0.8)',
        height=380,
        legend=dict(orientation='h', y=1.1),
        margin=dict(l=20, r=20, t=60, b=40)
    )
    return fig


def candidate_ranking_table(applications: list) -> pd.DataFrame:
    """Build a ranked DataFrame for provider's candidate view."""
    rows = []
    for app in applications:
        skills = app.get('extracted_skills', [])
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except Exception:
                skills = []
        rows.append({
            "Rank": 0,
            "Candidate": app.get('seeker_name', 'N/A'),
            "Email": app.get('email', ''),
            "Match Score": f"{round(app.get('match_score', 0))}%",
            "Match Score Raw": app.get('match_score', 0),
            "Skills Count": len(skills),
            "Status": app.get('status', 'applied').capitalize(),
            "Applied At": str(app.get('applied_at', ''))[:10],
            "App ID": app.get('id')
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('Match Score Raw', ascending=False).reset_index(drop=True)
        df['Rank'] = df.index + 1
        df = df.drop(columns=['Match Score Raw', 'App ID'])
    return df


def improvement_roadmap_chart(gap_analysis: list) -> go.Figure:
    """Bubble chart showing skills to improve, sized by importance."""
    if not gap_analysis:
        return go.Figure()

    importance_map = {"High": 40, "Medium": 25, "Low": 15}
    color_map = {"High": '#ef4444', "Medium": '#f59e0b', "Low": '#3b82f6'}

    skills = [g.get('skill', '') for g in gap_analysis]
    categories = [g.get('category', 'General') for g in gap_analysis]
    importance = [g.get('importance', 'Medium') for g in gap_analysis]
    times = [g.get('estimated_time', '1 month') for g in gap_analysis]
    sizes = [importance_map.get(i, 20) for i in importance]
    colors = [color_map.get(i, '#6366f1') for i in importance]

    fig = go.Figure()
    for imp_level, color in color_map.items():
        mask = [i == imp_level for i in importance]
        if not any(mask):
            continue
        fig.add_trace(go.Scatter(
            x=[c for c, m in zip(categories, mask) if m],
            y=[s for s, m in zip(skills, mask) if m],
            mode='markers+text',
            name=f'{imp_level} Priority',
            marker=dict(
                size=[sz for sz, m in zip(sizes, mask) if m],
                color=color,
                opacity=0.8,
                line=dict(color='white', width=1)
            ),
            text=[t for t, m in zip(times, mask) if m],
            textposition='middle right',
            hovertemplate='<b>%{y}</b><br>Category: %{x}<br>Time: %{text}<extra></extra>'
        ))

    fig.update_layout(
        title="Skills to Improve — Priority Map",
        xaxis_title="Category",
        yaxis_title="Skill",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(248,248,248,0.8)',
        height=420,
        margin=dict(l=20, r=120, t=60, b=40),
        legend=dict(orientation='v', x=1.02, y=0.5)
    )
    return fig


def match_score_gauge(score: float) -> go.Figure:
    """Gauge chart for overall match score."""
    color = '#10b981' if score >= 70 else '#f59e0b' if score >= 40 else '#ef4444'
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        delta={'reference': 70, 'increasing': {'color': '#10b981'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 40], 'color': 'rgba(239,68,68,0.15)'},
                {'range': [40, 70], 'color': 'rgba(245,158,11,0.15)'},
                {'range': [70, 100], 'color': 'rgba(16,185,129,0.15)'},
            ],
            'threshold': {'line': {'color': 'black', 'width': 2}, 'value': 70}
        },
        number={'suffix': "%", 'font': {'size': 36}},
        title={'text': "Match Score", 'font': {'size': 16}}
    ))
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig
