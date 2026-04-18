# Python Judge Backend Prototype

This backend is a starter for a HackerRank-like Python practice platform.

## What it does

- creates or restores student sessions with name and email
- serves challenge metadata to the frontend
- accepts student submissions through `POST /api/submissions`
- runs basic Python function challenges against test cases
- stores students and submissions in `backend/data/judge.db`

## Important warning

This is a local prototype for trusted development only.

It is **not** safe to expose arbitrary code execution directly to the internet. For a real student platform, run code inside isolated containers with strict CPU, memory, network, and filesystem limits.

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

4. Open `platform.html` in the site and submit code from the form.

## API shape

`POST /api/students/login`

```json
{
  "name": "Arjun",
  "email": "arjun@example.com"
}
```

`POST /api/submissions`

```json
{
  "student_id": 1,
  "challenge_id": "sum-two-numbers",
  "code": "def solve(a, b):\n    return a + b"
}
```

## Storage options from here

- Keep using SQLite for the MVP.
- Export `judge.db` data or sync it into Google Drive manually or with a small script.
- Upgrade later to SQLite, PostgreSQL, or Google Sheets depending on the scale.

## Recommended next step

Once the product flow feels right, move execution into Docker containers and store metadata in a proper database.
