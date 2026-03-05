import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "career_genie"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )

def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('seeker', 'provider')),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Seeker profiles
    cur.execute("""
        CREATE TABLE IF NOT EXISTS seeker_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            resume_text TEXT,
            extracted_skills JSONB DEFAULT '[]',
            resume_file_name VARCHAR(255),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Provider profiles
    cur.execute("""
        CREATE TABLE IF NOT EXISTS provider_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            company_name VARCHAR(255),
            industry VARCHAR(100),
            website VARCHAR(255),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Job postings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_postings (
            id SERIAL PRIMARY KEY,
            provider_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            required_skills JSONB DEFAULT '[]',
            tech_stack JSONB DEFAULT '[]',
            experience_level VARCHAR(50),
            location VARCHAR(150),
            interview_config JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Applications
    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id SERIAL PRIMARY KEY,
            seeker_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            job_id INTEGER REFERENCES job_postings(id) ON DELETE CASCADE,
            match_score FLOAT DEFAULT 0,
            status VARCHAR(50) DEFAULT 'applied',
            applied_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(seeker_id, job_id)
        );
    """)

    # Interviews
    cur.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            id SERIAL PRIMARY KEY,
            application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
            seeker_id INTEGER REFERENCES users(id),
            job_id INTEGER REFERENCES job_postings(id),
            questions JSONB DEFAULT '[]',
            answers JSONB DEFAULT '[]',
            scores JSONB DEFAULT '[]',
            total_score FLOAT DEFAULT 0,
            max_score FLOAT DEFAULT 0,
            feedback TEXT,
            status VARCHAR(30) DEFAULT 'pending',
            completed_at TIMESTAMP
        );
    """)

    # Messages
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            receiver_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            job_id INTEGER REFERENCES job_postings(id) ON DELETE SET NULL,
            content TEXT NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            sent_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Skill gap history (for dashboard comparison)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS skill_gap_history (
            id SERIAL PRIMARY KEY,
            seeker_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            target_role VARCHAR(255),
            match_score FLOAT,
            matched_skills JSONB DEFAULT '[]',
            missing_skills JSONB DEFAULT '[]',
            gap_analysis JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Roadmap progress
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roadmap_progress (
            id SERIAL PRIMARY KEY,
            seeker_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            target_role VARCHAR(255),
            skill VARCHAR(255),
            status VARCHAR(30) DEFAULT 'not_started',
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(seeker_id, target_role, skill)
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized successfully.")


# ─── Generic Helpers ──────────────────────────────────────────────────────────

def fetch_one(query, params=()):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(query, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None

def fetch_all(query, params=()):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

def execute(query, params=()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    last_id = None
    try:
        last_id = cur.fetchone()[0]
    except Exception:
        pass
    cur.close()
    conn.close()
    return last_id


# ─── User Queries ──────────────────────────────────────────────────────────────

def create_user(name, email, password_hash, role):
    return execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s,%s,%s,%s) RETURNING id",
        (name, email, password_hash, role)
    )

def get_user_by_email(email):
    return fetch_one("SELECT * FROM users WHERE email=%s", (email,))

def get_user_by_id(user_id):
    return fetch_one("SELECT * FROM users WHERE id=%s", (user_id,))


# ─── Seeker Profile ────────────────────────────────────────────────────────────

def upsert_seeker_profile(user_id, resume_text, extracted_skills, file_name):
    import json
    execute("""
        INSERT INTO seeker_profiles (user_id, resume_text, extracted_skills, resume_file_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET resume_text=EXCLUDED.resume_text,
            extracted_skills=EXCLUDED.extracted_skills,
            resume_file_name=EXCLUDED.resume_file_name,
            updated_at=NOW()
    """, (user_id, resume_text, json.dumps(extracted_skills), file_name))

def get_seeker_profile(user_id):
    return fetch_one("SELECT * FROM seeker_profiles WHERE user_id=%s", (user_id,))


# ─── Provider Profile ──────────────────────────────────────────────────────────

def upsert_provider_profile(user_id, company_name, industry, website):
    execute("""
        INSERT INTO provider_profiles (user_id, company_name, industry, website)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (user_id) DO UPDATE
        SET company_name=EXCLUDED.company_name,
            industry=EXCLUDED.industry,
            website=EXCLUDED.website,
            updated_at=NOW()
    """, (user_id, company_name, industry, website))

def get_provider_profile(user_id):
    return fetch_one("SELECT * FROM provider_profiles WHERE user_id=%s", (user_id,))


# ─── Job Postings ──────────────────────────────────────────────────────────────

def create_job(provider_id, title, description, required_skills, tech_stack,
               experience_level, location, interview_config):
    import json
    return execute("""
        INSERT INTO job_postings
        (provider_id, title, description, required_skills, tech_stack,
         experience_level, location, interview_config)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (provider_id, title, description,
          json.dumps(required_skills), json.dumps(tech_stack),
          experience_level, location, json.dumps(interview_config)))

def get_all_active_jobs():
    return fetch_all("""
        SELECT jp.*, u.name as provider_name, pp.company_name
        FROM job_postings jp
        JOIN users u ON jp.provider_id = u.id
        LEFT JOIN provider_profiles pp ON pp.user_id = u.id
        WHERE jp.is_active = TRUE
        ORDER BY jp.created_at DESC
    """)

def get_jobs_by_provider(provider_id):
    return fetch_all(
        "SELECT * FROM job_postings WHERE provider_id=%s ORDER BY created_at DESC",
        (provider_id,)
    )

def get_job_by_id(job_id):
    return fetch_one("SELECT * FROM job_postings WHERE id=%s", (job_id,))

def toggle_job_status(job_id, is_active):
    execute("UPDATE job_postings SET is_active=%s WHERE id=%s", (is_active, job_id))


# ─── Applications ──────────────────────────────────────────────────────────────

def apply_to_job(seeker_id, job_id, match_score):
    return execute("""
        INSERT INTO applications (seeker_id, job_id, match_score)
        VALUES (%s,%s,%s)
        ON CONFLICT (seeker_id, job_id) DO NOTHING
        RETURNING id
    """, (seeker_id, job_id, match_score))

def get_applications_by_seeker(seeker_id):
    return fetch_all("""
        SELECT a.*, jp.title, jp.description, jp.tech_stack, jp.location,
               pp.company_name, u.name as provider_name
        FROM applications a
        JOIN job_postings jp ON a.job_id = jp.id
        JOIN users u ON jp.provider_id = u.id
        LEFT JOIN provider_profiles pp ON pp.user_id = u.id
        WHERE a.seeker_id=%s ORDER BY a.applied_at DESC
    """, (seeker_id,))

def get_applications_by_job(job_id):
    return fetch_all("""
        SELECT a.*, u.name as seeker_name, u.email,
               sp.extracted_skills, sp.resume_text, sp.resume_file_name
        FROM applications a
        JOIN users u ON a.seeker_id = u.id
        LEFT JOIN seeker_profiles sp ON sp.user_id = u.id
        WHERE a.job_id=%s ORDER BY a.match_score DESC
    """, (job_id,))

def update_application_status(app_id, status):
    execute("UPDATE applications SET status=%s WHERE id=%s", (status, app_id))

def get_application(seeker_id, job_id):
    return fetch_one(
        "SELECT * FROM applications WHERE seeker_id=%s AND job_id=%s",
        (seeker_id, job_id)
    )


# ─── Interviews ────────────────────────────────────────────────────────────────

def create_interview(application_id, seeker_id, job_id, questions, max_score):
    import json
    return execute("""
        INSERT INTO interviews (application_id, seeker_id, job_id, questions, max_score)
        VALUES (%s,%s,%s,%s,%s) RETURNING id
    """, (application_id, seeker_id, job_id, json.dumps(questions), max_score))

def get_interview(interview_id):
    return fetch_one("SELECT * FROM interviews WHERE id=%s", (interview_id,))

def get_interview_by_application(application_id):
    return fetch_one("SELECT * FROM interviews WHERE application_id=%s", (application_id,))

def save_interview_results(interview_id, answers, scores, total_score, feedback):
    import json
    execute("""
        UPDATE interviews
        SET answers=%s, scores=%s, total_score=%s, feedback=%s,
            status='completed', completed_at=NOW()
        WHERE id=%s
    """, (json.dumps(answers), json.dumps(scores), total_score, feedback, interview_id))

def get_interviews_by_seeker(seeker_id):
    return fetch_all("""
        SELECT i.*, jp.title as job_title, pp.company_name
        FROM interviews i
        JOIN job_postings jp ON i.job_id = jp.id
        JOIN users u ON jp.provider_id = u.id
        LEFT JOIN provider_profiles pp ON pp.user_id = u.id
        WHERE i.seeker_id=%s ORDER BY i.completed_at DESC
    """, (seeker_id,))


# ─── Messages ──────────────────────────────────────────────────────────────────

def send_message(sender_id, receiver_id, job_id, content):
    return execute("""
        INSERT INTO messages (sender_id, receiver_id, job_id, content)
        VALUES (%s,%s,%s,%s) RETURNING id
    """, (sender_id, receiver_id, job_id, content))

def get_conversation(user1_id, user2_id, job_id=None):
    if job_id:
        return fetch_all("""
            SELECT m.*, u.name as sender_name
            FROM messages m JOIN users u ON m.sender_id=u.id
            WHERE ((m.sender_id=%s AND m.receiver_id=%s)
                OR (m.sender_id=%s AND m.receiver_id=%s))
            AND m.job_id=%s
            ORDER BY m.sent_at ASC
        """, (user1_id, user2_id, user2_id, user1_id, job_id))
    return fetch_all("""
        SELECT m.*, u.name as sender_name
        FROM messages m JOIN users u ON m.sender_id=u.id
        WHERE (m.sender_id=%s AND m.receiver_id=%s)
           OR (m.sender_id=%s AND m.receiver_id=%s)
        ORDER BY m.sent_at ASC
    """, (user1_id, user2_id, user2_id, user1_id))

def get_inbox(user_id):
    return fetch_all("""
        SELECT DISTINCT ON (LEAST(m.sender_id, m.receiver_id), GREATEST(m.sender_id, m.receiver_id), m.job_id)
            m.*, u.name as other_name, jp.title as job_title
        FROM messages m
        JOIN users u ON u.id = CASE WHEN m.sender_id=%s THEN m.receiver_id ELSE m.sender_id END
        LEFT JOIN job_postings jp ON m.job_id=jp.id
        WHERE m.sender_id=%s OR m.receiver_id=%s
        ORDER BY LEAST(m.sender_id, m.receiver_id), GREATEST(m.sender_id, m.receiver_id),
                 m.job_id, m.sent_at DESC
    """, (user_id, user_id, user_id))

def mark_messages_read(sender_id, receiver_id):
    execute("""
        UPDATE messages SET is_read=TRUE
        WHERE sender_id=%s AND receiver_id=%s AND is_read=FALSE
    """, (sender_id, receiver_id))

def get_unread_count(user_id):
    result = fetch_one(
        "SELECT COUNT(*) as cnt FROM messages WHERE receiver_id=%s AND is_read=FALSE",
        (user_id,)
    )
    return result['cnt'] if result else 0

# ─── Skill Gap History ─────────────────────────────────────────────────────────

def save_skill_gap(seeker_id, target_role, match_score, matched_skills, missing_skills, gap_analysis):
    import json
    return execute("""
        INSERT INTO skill_gap_history
        (seeker_id, target_role, match_score, matched_skills, missing_skills, gap_analysis)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
    """, (seeker_id, target_role, match_score,
          json.dumps(matched_skills), json.dumps(missing_skills), json.dumps(gap_analysis)))

def get_skill_gap_history(seeker_id, limit=10):
    return fetch_all("""
        SELECT * FROM skill_gap_history
        WHERE seeker_id=%s ORDER BY created_at DESC LIMIT %s
    """, (seeker_id, limit))

def get_latest_two_gaps(seeker_id, target_role):
    return fetch_all("""
        SELECT * FROM skill_gap_history
        WHERE seeker_id=%s AND target_role=%s
        ORDER BY created_at DESC LIMIT 2
    """, (seeker_id, target_role))


# ─── Roadmap Progress ──────────────────────────────────────────────────────────

def upsert_roadmap_progress(seeker_id, target_role, skill, status):
    execute("""
        INSERT INTO roadmap_progress (seeker_id, target_role, skill, status)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (seeker_id, target_role, skill)
        DO UPDATE SET status=EXCLUDED.status, updated_at=NOW()
    """, (seeker_id, target_role, skill, status))

def get_roadmap_progress(seeker_id, target_role):
    rows = fetch_all("""
        SELECT skill, status FROM roadmap_progress
        WHERE seeker_id=%s AND target_role=%s
    """, (seeker_id, target_role))
    return {r['skill']: r['status'] for r in rows}
