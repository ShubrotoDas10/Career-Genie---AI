import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


def _chat(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    """Base chat completion call."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=4096,
    )
    return response.choices[0].message.content.strip()


def _parse_json(text: str) -> any:
    """Safely extract JSON from model response."""
    try:
        # Try direct parse
        return json.loads(text)
    except Exception:
        # Try extracting from code block
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except Exception:
                pass
    return None


# ─── 1. Resume Skill Extraction ────────────────────────────────────────────────

def extract_skills_from_resume(resume_text: str) -> dict:
    """
    Returns:
    {
      "skills": ["Python", "SQL", ...],
      "experience_years": 3,
      "education": "B.Tech Computer Science",
      "job_titles": ["Software Engineer", ...],
      "summary": "..."
    }
    """
    system = """You are an expert resume parser. Extract structured information from resumes.
Always respond with valid JSON only, no extra text."""

    prompt = f"""Parse this resume and return a JSON object with:
- "skills": list of technical and soft skills found
- "experience_years": estimated years of experience (integer)
- "education": highest education qualification as string
- "job_titles": list of job titles/roles held
- "summary": 2-sentence professional summary

Resume text:
{resume_text[:6000]}

Return only valid JSON."""

    result = _chat(system, prompt)
    parsed = _parse_json(result)
    if not parsed:
        return {"skills": [], "experience_years": 0, "education": "", "job_titles": [], "summary": ""}
    return parsed


# ─── 2. Job Skill Extraction ───────────────────────────────────────────────────

def extract_skills_from_jd(job_description: str) -> list:
    """Extract required skills from a job description."""
    system = "You are an expert job description analyzer. Return only valid JSON."
    prompt = f"""Extract all required and preferred skills from this job description.
Return a JSON array of skill strings only.

Job Description:
{job_description[:4000]}

Return only a JSON array like: ["Python", "SQL", "React"]"""

    result = _chat(system, prompt)
    parsed = _parse_json(result)
    return parsed if isinstance(parsed, list) else []


# ─── 3. Match Score ────────────────────────────────────────────────────────────

def compute_match_score(seeker_skills: list, job_skills: list, job_description: str) -> dict:
    """
    Returns:
    {
      "score": 75,
      "matched_skills": [...],
      "missing_skills": [...],
      "verdict": "Strong Match"
    }
    """
    system = "You are a career matching expert. Return only valid JSON."
    prompt = f"""Compare a candidate's skills with a job's requirements.

Candidate Skills: {json.dumps(seeker_skills)}
Job Required Skills: {json.dumps(job_skills)}
Job Description (context): {job_description[:1500]}

Return a JSON object with:
- "score": integer 0-100 match percentage
- "matched_skills": list of skills candidate has that match
- "missing_skills": list of required skills candidate lacks
- "verdict": one of "Excellent Match", "Strong Match", "Moderate Match", "Weak Match"

Return only valid JSON."""

    result = _chat(system, prompt)
    parsed = _parse_json(result)
    if not parsed:
        return {"score": 0, "matched_skills": [], "missing_skills": job_skills, "verdict": "Weak Match"}
    return parsed


# ─── 4. Skill Gap Analysis ─────────────────────────────────────────────────────

def analyze_skill_gap(seeker_skills: list, missing_skills: list, target_role: str) -> dict:
    """
    Returns:
    {
      "gap_analysis": [
        {
          "skill": "Docker",
          "importance": "High",
          "category": "DevOps",
          "why_needed": "...",
          "why_deducted": "...",
          "how_to_improve": "...",
          "learning_resources": [...],
          "estimated_time": "2 weeks",
          "prerequisite": "Linux basics"
        }, ...
      ],
      "ordered_roadmap": [{"step": 1, "skill": "...", "reason": "..."}],
      "roadmap": "...",
      "priority_skills": [...]
    }
    """
    system = "You are a senior career coach and skills development expert. Return only valid JSON."
    prompt = f"""A candidate wants to become a {target_role}.
They have: {json.dumps(seeker_skills)}
They are missing: {json.dumps(missing_skills)}

Provide a detailed skill gap analysis as JSON with:
- "gap_analysis": array of objects, each with:
  - "skill": skill name
  - "importance": "High", "Medium", or "Low"
  - "category": skill category (e.g., "Backend", "DevOps", "Soft Skills")
  - "why_needed": why this skill is essential for {target_role} (1-2 sentences)
  - "why_deducted": what specifically they are missing / why it hurts their profile (1-2 sentences)
  - "how_to_improve": concrete actionable advice to gain this skill (2-3 sentences)
  - "learning_resources": list of 3 specific resources (course name + platform, e.g. "Python for Everybody – Coursera")
  - "estimated_time": how long to learn realistically (e.g., "2 weeks", "1 month")
  - "prerequisite": what to learn before this (or "None")
- "ordered_roadmap": array of objects in the exact order skills should be learned:
  - "step": integer
  - "skill": skill name
  - "reason": why this comes before the next one (1 sentence)
  - "milestone": what you can do after learning this
- "roadmap": 3-4 sentence overall learning strategy paragraph
- "priority_skills": ordered list of top 5 skills to learn first

Return only valid JSON."""

    result = _chat(system, prompt, temperature=0.4)
    parsed = _parse_json(result)
    if not parsed:
        return {"gap_analysis": [], "ordered_roadmap": [], "roadmap": "", "priority_skills": missing_skills[:5]}
    return parsed


# ─── 5. Generate Interview Questions ───────────────────────────────────────────

def generate_interview_questions(config: dict) -> list:
    """
    config = {
      "job_title": "...",
      "tech_stack": [...],
      "behavioral_count": 3,
      "technical_count": 5,
      "coding_count": 2,
      "difficulty": "Medium",
      "marks_per_behavioral": 5,
      "marks_per_technical": 10,
      "marks_per_coding": 15,
    }
    Returns list of question objects.
    """
    system = "You are an expert technical interviewer. Return only valid JSON."
    prompt = f"""Generate interview questions for a {config.get('job_title')} role.

Tech Stack: {json.dumps(config.get('tech_stack', []))}
Difficulty: {config.get('difficulty', 'Medium')}

Generate exactly:
- {config.get('behavioral_count', 0)} behavioral questions
- {config.get('technical_count', 0)} technical questions
- {config.get('coding_count', 0)} coding/problem-solving questions

Return a JSON array where each question object has:
- "id": sequential integer starting from 1
- "type": "behavioral", "technical", or "coding"
- "question": the question text
- "marks": {config.get('marks_per_behavioral', 5)} for behavioral, {config.get('marks_per_technical', 10)} for technical, {config.get('marks_per_coding', 15)} for coding
- "hint": a brief hint or what to look for in the answer
- "expected_keywords": list of 3-5 keywords expected in a good answer

Return only valid JSON array."""

    result = _chat(system, prompt, temperature=0.6)
    parsed = _parse_json(result)
    return parsed if isinstance(parsed, list) else []


# ─── 6. Evaluate Interview Answer ──────────────────────────────────────────────

def evaluate_answer(question: str, q_type: str, answer: str, max_marks: int,
                    expected_keywords: list, tech_stack: list) -> dict:
    """
    Returns:
    {
      "score": 8,
      "feedback": "...",
      "strengths": [...],
      "improvements": [...]
    }
    """
    system = "You are a strict but fair technical interviewer. Return only valid JSON."
    prompt = f"""Evaluate this interview answer.

Question ({q_type}): {question}
Expected Keywords: {json.dumps(expected_keywords)}
Tech Stack Context: {json.dumps(tech_stack)}
Max Marks: {max_marks}

Candidate's Answer: {answer}

Score the answer out of {max_marks} and return JSON with:
- "score": integer score out of {max_marks}
- "feedback": 2-3 sentence detailed feedback
- "strengths": list of 1-3 things done well
- "improvements": list of 1-3 things to improve

Be strict but constructive. Return only valid JSON."""

    result = _chat(system, prompt, temperature=0.2)
    parsed = _parse_json(result)
    if not parsed:
        return {"score": 0, "feedback": "Could not evaluate.", "strengths": [], "improvements": []}
    return parsed


# ─── 7. Overall Interview Feedback ─────────────────────────────────────────────

def generate_interview_summary(job_title: str, questions: list, answers: list,
                                scores: list, total: float, max_total: float) -> str:
    """Generate a comprehensive interview performance summary."""
    system = "You are an expert career coach providing post-interview feedback."
    prompt = f"""A candidate completed a mock interview for {job_title}.

Total Score: {total}/{max_total} ({round(total/max_total*100)}%)

Questions and Scores:
{json.dumps([{"q": q.get('question'), "type": q.get('type'), "score": s.get('score'), "max": q.get('marks')} for q, s in zip(questions, scores)], indent=2)[:3000]}

Write a comprehensive 4-6 paragraph performance summary covering:
1. Overall performance assessment
2. Strongest areas
3. Areas needing improvement
4. Specific advice for the {job_title} role
5. Next steps and encouragement

Write in a professional, encouraging tone."""

    return _chat(system, prompt, temperature=0.5)


# ─── 8. Suggest Matching Roles from Resume ────────────────────────────────────

def suggest_roles_from_resume(skills: list, job_titles: list, experience_years: int,
                               level_filter: str = "All") -> list:
    """
    Given a seeker's extracted skills + past job titles, suggest best-fit roles.
    level_filter: "All", "Intern", "Junior", "Mid-Level", "Senior"
    Returns list of role strings ordered by fit.
    """
    system = "You are a career advisor. Return only valid JSON."

    level_instruction = ""
    if level_filter == "Intern":
        level_instruction = "Only suggest internship or entry-level roles (0-1 years experience). Include 'Intern' or 'Trainee' in titles."
    elif level_filter == "Junior":
        level_instruction = "Only suggest junior/associate roles (1-3 years experience). Include 'Junior', 'Associate', or 'Entry' in titles."
    elif level_filter == "Mid-Level":
        level_instruction = "Only suggest mid-level roles (3-6 years experience). No intern or senior titles."
    elif level_filter == "Senior":
        level_instruction = "Only suggest senior, lead, or principal roles (6+ years experience)."
    else:
        level_instruction = "Include a balanced mix across Intern, Junior, Mid-Level, and Senior roles — label each clearly."

    prompt = f"""A job seeker has the following profile:
Skills: {json.dumps(skills)}
Past Titles: {json.dumps(job_titles)}
Experience: {experience_years} years

Level Filter: {level_filter}
{level_instruction}

Suggest exactly 12 specific job role titles they are best suited for.
Return a JSON array of role title strings only, ordered from best fit to stretch goal.
Be specific and varied — e.g. "Associate Data Scientist", "ML Engineer (NLP)", "Computer Vision Engineer"
Do NOT repeat similar titles. Cover different specializations within the level.

Return only a JSON array of 12 strings."""
    result = _chat(system, prompt, temperature=0.5)
    parsed = _parse_json(result)
    return parsed if isinstance(parsed, list) else []


# ─── 9. Generate 5-Level Progressive Interview Questions ──────────────────────

LEVEL_CONFIG = {
    1: {
        "label": "Foundations",
        "description": "Core concepts, definitions, basic usage",
        "question_types": ["conceptual", "behavioral", "technical"],
        "difficulty": "Easy",
        "marks": 5,
        "count": 4,
    },
    2: {
        "label": "Practical Application",
        "description": "Real-world usage, common patterns, tool familiarity",
        "question_types": ["technical", "scenario", "behavioral"],
        "difficulty": "Easy-Medium",
        "marks": 8,
        "count": 4,
    },
    3: {
        "label": "Problem Solving",
        "description": "Debugging, use cases, trade-offs, system design basics",
        "question_types": ["debugging", "use_case", "technical", "coding"],
        "difficulty": "Medium",
        "marks": 12,
        "count": 5,
    },
    4: {
        "label": "Advanced & Architecture",
        "description": "Optimization, architecture decisions, edge cases, advanced coding",
        "question_types": ["architecture", "coding", "debugging", "use_case"],
        "difficulty": "Medium-Hard",
        "marks": 15,
        "count": 4,
    },
    5: {
        "label": "Expert & Leadership",
        "description": "System design, leadership scenarios, complex tradeoffs, expert coding",
        "question_types": ["system_design", "coding", "leadership", "architecture"],
        "difficulty": "Hard",
        "marks": 20,
        "count": 3,
    },
}

TYPE_DESCRIPTIONS = {
    "conceptual": "Ask about definitions, theory, how/why something works",
    "behavioral": "Ask about past experience using STAR format",
    "technical": "Ask about specific technical knowledge or implementation",
    "scenario": "Give a real-world scenario and ask how they'd handle it",
    "debugging": "Give broken code/system and ask them to find and fix the issue",
    "use_case": "Ask when/why they'd use a specific tool, pattern, or approach",
    "coding": "Ask them to write code or pseudocode to solve a problem",
    "architecture": "Ask about designing a system component or making tech decisions",
    "system_design": "Ask about designing a full system end-to-end",
    "leadership": "Ask about leading teams, mentoring, resolving conflicts, decision-making",
}


def generate_leveled_questions(role: str, skills: list, missing_skills: list, level: int) -> list:
    """
    Generate questions for a specific interview level (1–5).
    Blends what the seeker knows (skills) with what they need to learn (missing_skills).
    Returns list of question objects.
    """
    cfg = LEVEL_CONFIG[level]
    system = "You are a senior technical interviewer. Return only valid JSON."

    # Mix known + unknown skills for richer coverage
    known_sample = skills[:8] if skills else []
    unknown_sample = missing_skills[:4] if missing_skills else []

    q_types_desc = "\n".join([f"- {t}: {TYPE_DESCRIPTIONS.get(t,'')}" for t in cfg['question_types']])

    prompt = f"""Generate {cfg['count']} interview questions for a **{role}** role at **Level {level}: {cfg['label']}**.

Level Description: {cfg['description']}
Difficulty: {cfg['difficulty']}

Candidate's Known Skills (focus here): {json.dumps(known_sample)}
Skills They Need to Learn (include 1-2 stretch questions): {json.dumps(unknown_sample)}

Question Types to use (distribute across these):
{q_types_desc}

Rules:
- Mix question types — don't use the same type twice in a row
- For debugging questions: include a short broken code snippet in the question
- For coding questions: give a clear problem statement with input/output example
- For use_case questions: name a specific technology from their stack
- Questions should build logically on each other within this level
- Stretch questions (from missing skills) should feel achievable, not impossible

Return a JSON array where each object has:
- "id": integer starting from 1
- "type": one of {json.dumps(cfg['question_types'])}
- "question": full question text (include code snippet if debugging/coding)
- "marks": {cfg['marks']}
- "hint": what a good answer should cover (1 sentence)
- "expected_keywords": list of 3-5 keywords/concepts expected in a good answer
- "is_stretch": true if this tests a missing skill, false otherwise

Return only valid JSON array."""

    result = _chat(system, prompt, temperature=0.65)
    parsed = _parse_json(result)
    if not isinstance(parsed, list):
        return []
    # Inject level metadata into each question
    for q in parsed:
        q['level'] = level
        q['level_label'] = cfg['label']
    return parsed


def generate_level_feedback(role: str, level: int, questions: list,
                             answers: list, scores: list) -> dict:
    """
    After completing a level, generate targeted feedback + readiness for next level.
    Returns { "summary": str, "ready_for_next": bool, "weak_areas": [], "strong_areas": [] }
    """
    system = "You are a senior career coach. Return only valid JSON."
    cfg = LEVEL_CONFIG[level]
    total = sum(s.get('score', 0) for s in scores)
    max_total = sum(q.get('marks', cfg['marks']) for q in questions)
    pct = round(total / max_total * 100) if max_total else 0

    prompt = f"""A candidate completed Level {level} ({cfg['label']}) of a {role} interview.
Score: {total}/{max_total} ({pct}%)

Questions and performance:
{json.dumps([{
    "q": q.get('question','')[:120],
    "type": q.get('type',''),
    "is_stretch": q.get('is_stretch', False),
    "score": s.get('score', 0),
    "max": q.get('marks', cfg['marks']),
    "feedback": s.get('feedback','')[:100]
} for q, s in zip(questions, scores)], indent=2)[:3000]}

Return a JSON object with:
- "summary": 2-3 sentence level summary
- "ready_for_next": true if score >= 60%, false otherwise
- "strong_areas": list of 2-3 topics they did well on
- "weak_areas": list of 2-3 topics to revisit before next level
- "encouragement": one motivating sentence

Return only valid JSON."""

    result = _chat(system, prompt, temperature=0.4)
    parsed = _parse_json(result)
    if not parsed:
        return {
            "summary": "Level completed.",
            "ready_for_next": pct >= 60,
            "strong_areas": [],
            "weak_areas": [],
            "encouragement": "Keep going!"
        }
    return parsed


def get_upskilling_recommendations(current_skills: list, target_role: str,
                                    experience_years: int) -> dict:
    """Returns structured upskilling plan with ordered roadmap, courses and timelines."""
    system = "You are a career development expert. Return only valid JSON."
    prompt = f"""Create a comprehensive upskilling plan for someone who wants to be a {target_role}.

Current Skills: {json.dumps(current_skills)}
Experience: {experience_years} years

Return JSON with:
- "short_term": list of 3 skills for 1-3 months, each with:
  "skill", "why", "resource", "what_you_can_do_after", "topics": [list of 4-5 sub-topics to study in order]
- "medium_term": list of 3 skills for 3-6 months, same structure
- "long_term": list of 2 skills for 6-12 months, same structure
- "ordered_roadmap": array of all skills in the exact order to learn them:
  each has "step", "skill", "timeframe", "depends_on" (previous skill or "Start here"), "why_this_order"
- "certifications": list of 3 relevant certifications each with "name", "provider", "why_useful"
- "projects": list of 3 project ideas each with "name", "description", "skills_practiced", "difficulty"

Return only valid JSON."""

    result = _chat(system, prompt, temperature=0.4)
    parsed = _parse_json(result)
    if not parsed:
        return {"short_term": [], "medium_term": [], "long_term": [],
                "ordered_roadmap": [], "certifications": [], "projects": []}
    return parsed
