import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "judge.db"
CODE_ARCHIVE_DIR = DATA_DIR / "code_archive"


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
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                student_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id)
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
                duration_minutes INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                challenge_id TEXT NOT NULL,
                status TEXT NOT NULL,
                focus_warnings INTEGER NOT NULL DEFAULT 0,
                fullscreen_exits INTEGER NOT NULL DEFAULT 0,
                latest_code TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                submitted_at TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(challenge_id) REFERENCES challenges(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_session_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                challenge_id TEXT NOT NULL,
                code TEXT NOT NULL,
                status TEXT NOT NULL,
                passed_tests INTEGER NOT NULL,
                total_tests INTEGER NOT NULL,
                results_json TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                FOREIGN KEY(test_session_id) REFERENCES test_sessions(id),
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(challenge_id) REFERENCES challenges(id)
            )
            """
        )
        _ensure_column(connection, "students", "password_hash", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "challenges", "duration_minutes", "INTEGER NOT NULL DEFAULT 30")
        _ensure_column(connection, "submissions", "test_session_id", "INTEGER NOT NULL DEFAULT 0")

        for challenge_id, challenge in challenges.items():
            connection.execute(
                """
                INSERT INTO challenges (
                    id, title, description, function_name, starter_code,
                    visible_tests_json, duration_minutes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    function_name = excluded.function_name,
                    starter_code = excluded.starter_code,
                    visible_tests_json = excluded.visible_tests_json,
                    duration_minutes = excluded.duration_minutes,
                    updated_at = excluded.updated_at
                """,
                (
                    challenge_id,
                    challenge["title"],
                    challenge["description"],
                    challenge["function_name"],
                    challenge["starter_code"],
                    json.dumps(challenge["visible_tests"]),
                    challenge["duration_minutes"],
                    utc_now(),
                ),
            )


def register_student(name, email, password):
    timestamp = utc_now()
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM students WHERE email = ?",
            (email,),
        ).fetchone()
        if existing:
            raise ValueError("An account with this email already exists.")

        cursor = connection.execute(
            """
            INSERT INTO students (name, email, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, email, generate_password_hash(password), timestamp, timestamp),
        )
        student_id = cursor.lastrowid
    return get_student(student_id)


def authenticate_student(email, password):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, name, email, password_hash, created_at, updated_at
            FROM students
            WHERE email = ?
            """,
            (email,),
        ).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_auth_token(student_id):
    token = secrets.token_urlsafe(32)
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO auth_tokens (token, student_id, created_at)
            VALUES (?, ?, ?)
            """,
            (token, student_id, utc_now()),
        )
    return token


def get_student_by_token(token):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT s.id, s.name, s.email, s.created_at, s.updated_at
            FROM auth_tokens t
            JOIN students s ON s.id = t.student_id
            WHERE t.token = ?
            """,
            (token,),
        ).fetchone()
    return dict(row) if row else None


def get_student(student_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, name, email, created_at, updated_at
            FROM students
            WHERE id = ?
            """,
            (student_id,),
        ).fetchone()
    return dict(row) if row else None


def get_challenges():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, description, function_name, starter_code,
                   visible_tests_json, duration_minutes
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
                "duration_minutes": row["duration_minutes"],
            }
        )
    return items


def get_challenge(challenge_id):
    for challenge in get_challenges():
        if challenge["id"] == challenge_id:
            return challenge
    return None


def create_test_session(student_id, challenge_id):
    timestamp = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO test_sessions (
                student_id, challenge_id, status, focus_warnings, fullscreen_exits,
                latest_code, started_at, updated_at
            )
            VALUES (?, ?, 'in_progress', 0, 0, '', ?, ?)
            """,
            (student_id, challenge_id, timestamp, timestamp),
        )
        session_id = cursor.lastrowid
    return get_test_session(session_id)


def get_test_session(session_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, student_id, challenge_id, status, focus_warnings, fullscreen_exits,
                   latest_code, started_at, updated_at, submitted_at
            FROM test_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def list_test_sessions_for_student(student_id):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, student_id, challenge_id, status, focus_warnings, fullscreen_exits,
                   latest_code, started_at, updated_at, submitted_at
            FROM test_sessions
            WHERE student_id = ?
            ORDER BY id DESC
            """,
            (student_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_test_session_activity(session_id, latest_code, focus_warnings, fullscreen_exits):
    timestamp = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE test_sessions
            SET latest_code = ?, focus_warnings = ?, fullscreen_exits = ?, updated_at = ?
            WHERE id = ?
            """,
            (latest_code, focus_warnings, fullscreen_exits, timestamp, session_id),
        )
    return get_test_session(session_id)


def mark_test_session_submitted(session_id, latest_code, focus_warnings, fullscreen_exits):
    timestamp = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE test_sessions
            SET status = 'submitted',
                latest_code = ?,
                focus_warnings = ?,
                fullscreen_exits = ?,
                updated_at = ?,
                submitted_at = ?
            WHERE id = ?
            """,
            (latest_code, focus_warnings, fullscreen_exits, timestamp, timestamp, session_id),
        )
    return get_test_session(session_id)


def save_submission(record):
    submitted_at = utc_now()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO submissions (
                test_session_id, student_id, challenge_id, code, status, passed_tests,
                total_tests, results_json, submitted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["test_session_id"],
                record["student_id"],
                record["challenge_id"],
                record["code"],
                record["status"],
                record["passed_tests"],
                record["total_tests"],
                json.dumps(record["results"]),
                submitted_at,
            ),
        )
        submission_id = cursor.lastrowid
        row = connection.execute(
            """
            SELECT id, test_session_id, student_id, challenge_id, code, status,
                   passed_tests, total_tests, results_json, submitted_at
            FROM submissions
            WHERE id = ?
            """,
            (submission_id,),
        ).fetchone()

    archive_submission_code(dict(row), submitted_at)
    return _submission_row_to_dict(row)


def list_submissions_for_student(student_id):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, test_session_id, student_id, challenge_id, code, status,
                   passed_tests, total_tests, results_json, submitted_at
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
    sessions = list_test_sessions_for_student(student_id)
    return {
        "total_submissions": len(submissions),
        "accepted_submissions": sum(1 for item in submissions if item["status"] == "accepted"),
        "solved_challenges": len(solved),
        "test_sessions": len(sessions),
    }


def archive_submission_code(submission_row, submitted_at):
    student_dir = CODE_ARCHIVE_DIR / f"student_{submission_row['student_id']}"
    student_dir.mkdir(parents=True, exist_ok=True)
    safe_time = submitted_at.replace(":", "-")
    file_path = student_dir / (
        f"{safe_time}_session_{submission_row['test_session_id']}_{submission_row['challenge_id']}.py"
    )
    file_path.write_text(submission_row["code"], encoding="utf-8")


def _submission_row_to_dict(row):
    row_dict = dict(row)
    return {
        "id": row_dict["id"],
        "test_session_id": row_dict["test_session_id"],
        "student_id": row_dict["student_id"],
        "challenge_id": row_dict["challenge_id"],
        "code": row_dict["code"],
        "status": row_dict["status"],
        "passed_tests": row_dict["passed_tests"],
        "total_tests": row_dict["total_tests"],
        "results": json.loads(row_dict["results_json"]),
        "submitted_at": row_dict["submitted_at"],
    }


def _ensure_column(connection, table_name, column_name, column_definition):
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {column["name"] for column in columns}
    if column_name not in existing:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )
