# snickr

A web-based team collaboration platform similar to Slack, built with FastAPI and MySQL.

## Features
- User registration and session-based login
- Create and manage workspaces
- Public, private, and direct message channels
- Invite members to workspaces and channels
- Admin controls: promote and remove members
- Keyword search across accessible channels
- SQL injection protection via parameterized queries
- XSS protection via Jinja2 auto-escaping

## Stack
- **Backend**: Python, FastAPI, Uvicorn
- **Database**: MySQL
- **Frontend**: Jinja2 templates, Vanilla CSS
- **Auth**: Signed session cookies (itsdangerous)

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your DB credentials
python3 -m uvicorn main:app --reload --port 8000
```

## Course
CS6083 — Principles of Database Systems  
NYU Tandon School of Engineering, Spring 2026
EOF

git add README.md
git commit -m "Add README"
git push