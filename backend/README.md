# Python Judge Backend Prototype

This backend is a starter for a HackerRank-like Python test platform with registration, login, exam sessions, autosave, and stored submission files.

## What it does

- supports registration and login with email and password
- issues auth tokens for the frontend
- creates coding test sessions per student
- autosaves current code and warning counters
- validates code to surface syntax and runtime issues
- evaluates final submissions against visible and hidden test cases
- stores students, sessions, and submissions in `backend/data/judge.db`
- archives each final Python file in `backend/data/code_archive/`

## Important warning

This is still not production-safe internet code execution.

It adds stronger exam-style workflow controls, but it does **not** fully prevent cheating. A browser app cannot guarantee that a student is not using another device, VM, or second screen. For real high-stakes assessments, use containerized execution, proctoring policy, and stronger identity checks.

## Quick start

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the API:

```bash
python app.py
```

4. Open `platform.html` in the site and register/login.

## API shape

`POST /api/auth/register`

```json
{
  "name": "Arjun",
  "email": "arjun@example.com",
  "password": "secret123"
}
```

`POST /api/auth/login`

```json
{
  "email": "arjun@example.com",
  "password": "secret123"
}
```

`POST /api/test-sessions`

```json
{
  "challenge_id": "sum-two-numbers"
}
```

`POST /api/code/check`

```json
{
  "challenge_id": "sum-two-numbers",
  "code": "def solve(a, b):\n    return a + b"
}
```

`POST /api/submissions`

```json
{
  "test_session_id": 1,
  "challenge_id": "sum-two-numbers",
  "code": "def solve(a, b):\n    return a + b",
  "focus_warnings": 1,
  "fullscreen_exits": 0
}
```

## Storage options from here

- Keep using SQLite for the MVP.
- Use `backend/data/code_archive/` when you want the raw Python files students submitted.
- Export `judge.db` data or sync it into Google Drive manually or with a small script.
- Upgrade later to PostgreSQL or a managed database if the number of students grows.

## Recommended next step

Once the product flow feels right, host the Flask API on a Python service and move execution into Docker containers before treating this as a real public exam system.
