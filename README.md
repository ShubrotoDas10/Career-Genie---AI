# 🧞 Career Genie — Setup Guide

## Prerequisites
- Python 3.10+
- PostgreSQL installed and running
- Groq API key (get free at https://console.groq.com)

---

## Step 1: Clone / Download the Project
```bash
cd career_genie
```

## Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 3: Set Up PostgreSQL Database
```sql
-- In psql or pgAdmin:
CREATE DATABASE career_genie;
```

## Step 4: Configure Environment Variables
```bash
cp .env.example .env
```

Edit `.env`:
```
GROQ_API_KEY=your_groq_api_key_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=career_genie
DB_USER=postgres
DB_PASSWORD=your_postgres_password
```

## Step 5: Run the App
```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Project Structure
```
career_genie/
├── app.py                    # Main entry point + routing
├── requirements.txt
├── .env                      # Your config (not committed)
├── auth/
│   ├── login.py              # Login page
│   └── signup.py             # Signup with role selection
├── seeker/
│   ├── dashboard.py          # Seeker overview + radar chart
│   ├── resume_upload.py      # PDF/DOCX upload + AI parsing
│   ├── job_match.py          # Browse jobs + apply
│   ├── skill_gap.py          # Gap analysis + heatmap + roadmap
│   ├── interview_room.py     # AI mock interview
│   └── messages.py           # Chat inbox
├── provider/
│   ├── dashboard.py          # Provider analytics dashboard
│   ├── post_job.py           # Post jobs + interview builder
│   ├── candidates.py         # View/rank/download candidates
│   └── messages.py           # Chat inbox
└── shared/
    ├── db.py                 # PostgreSQL layer (all queries)
    ├── groq_client.py        # All Groq AI calls
    ├── resume_parser.py      # PDF + DOCX text extraction
    └── analytics.py          # All Plotly charts
```

---

## Feature Overview

### 👤 Job Seeker
1. Sign up → upload resume (PDF/DOCX)
2. AI extracts skills, experience, education
3. Browse active job postings → see match score
4. View skill gap heatmap + learning roadmap
5. Take AI mock interview for any applied job
6. Message providers directly

### 🏢 Job Provider
1. Sign up → post jobs with full description
2. Configure custom interview:
   - Number of behavioral / technical / coding questions
   - Marks per question type
   - Passing threshold
   - Difficulty level
   - Tech stack focus
3. View AI-ranked candidate table
4. Update application status (shortlist, reject, hire)
5. Download candidate resumes
6. Message candidates directly

---

## Tech Stack
- **Frontend:** Streamlit
- **AI:** Groq (mixtral-8x7b-32768)
- **Database:** PostgreSQL
- **Resume Parsing:** PyMuPDF (PDF) + python-docx (DOCX)
- **Charts:** Plotly
- **Auth:** bcrypt password hashing
