import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "judge.db"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(challenges):
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS challenges (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                function_name TEXT NOT NULL,
                starter_code TEXT NOT NULL,
                visible_tests_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                challenge_id TEXT NOT NULL,
                code TEXT NOT NULL,
                status TEXT NOT NULL,
                passed_tests INTEGER NOT NULL,
                total_tests INTEGER NOT NULL,
                results_json TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(challenge_id) REFERENCES challenges(id)
            )
            """
        )

        for challenge_id, challenge in challenges.items():
            connection.execute(
                """
                INSERT INTO challenges (
                    id, title, description, function_name, starter_code,
                    visible_tests_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    function_name = excluded.function_name,
                    starter_code = excluded.starter_code,
                    visible_tests_json = excluded.visible_tests_json,
                    updated_at = excluded.updated_at
                """,
                (
                    challenge_id,
                    challenge["title"],
                    challenge["description"],
                    challenge["function_name"],
                    challenge["starter_code"],
                    json.dumps(challenge["visible_tests"]),
                    utc_now(),
                ),
            )


def get_challenges():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, description, function_name, starter_code, visible_tests_json
            FROM challenges
            ORDER BY title ASC
            """
        ).fetchall()
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "function_name": row["function_name"],
                "starter_code": row["starter_code"],
                "visible_tests": json.loads(row["visible_tests_json"]),
            }
        )
    return items


def upsert_student(name, email):
    timestamp = utc_now()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM students WHERE email = ?",
            (email,),
        ).fetchone()

        if row:
            connection.execute(
                """
                UPDATE students
                SET name = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, timestamp, row["id"]),
            )
            student_id = row["id"]
        else:
            cursor = connection.execute(
                """
                INSERT INTO students (name, email, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, timestamp, timestamp),
            )
            student_id = cursor.lastrowid

        student = connection.execute(
            "SELECT id, name, email, created_at, updated_at FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()
    return dict(student)


def get_student(student_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name, email, created_at, updated_at FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()
    return dict(row) if row else None


def save_submission(record):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO submissions (
                student_id, challenge_id, code, status, passed_tests, total_tests,
                results_json, submitted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["student_id"],
                record["challenge_id"],
                record["code"],
                record["status"],
                record["passed_tests"],
                record["total_tests"],
                json.dumps(record["results"]),
                utc_now(),
            ),
        )
        submission_id = cursor.lastrowid
        row = connection.execute(
            """
            SELECT id, student_id, challenge_id, code, status, passed_tests, total_tests,
                   results_json, submitted_at
            FROM submissions
            WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()
    return _submission_row_to_dict(row)


def list_submissions_for_student(student_id):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, student_id, challenge_id, code, status, passed_tests, total_tests,
                   results_json, submitted_at
            FROM submissions
            WHERE student_id = ?
            ORDER BY id DESC
            """,
            (student_id,),
        ).fetchall()
    return [_submission_row_to_dict(row) for row in rows]


def get_student_stats(student_id):
    submissions = list_submissions_for_student(student_id)
    solved = {item["challenge_id"] for item in submissions if item["status"] == "accepted"}
    return {
        "total_submissions": len(submissions),
        "accepted_submissions": sum(1 for item in submissions if item["status"] == "accepted"),
        "solved_challenges": len(solved),
    }


def _submission_row_to_dict(row):
    return {
        "id": row["id"],
        "student_id": row["student_id"],
        "challenge_id": row["challenge_id"],
        "code": row["code"],
        "status": row["status"],
        "passed_tests": row["passed_tests"],
        "total_tests": row["total_tests"],
        "results": json.loads(row["results_json"]),
        "submitted_at": row["submitted_at"],
    }
