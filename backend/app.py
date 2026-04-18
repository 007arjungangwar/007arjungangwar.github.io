from functools import wraps
import os

from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    from challenges import CHALLENGES, evaluate_submission, validate_submission
    from storage import (
        authenticate_student,
        create_auth_token,
        create_test_session,
        get_challenges,
        get_student,
        get_student_by_token,
        get_student_stats,
        get_test_session,
        init_db,
        list_submissions_for_student,
        list_test_sessions_for_student,
        mark_test_session_submitted,
        register_student,
        save_submission,
        update_test_session_activity,
    )
except ImportError:
    from .challenges import CHALLENGES, evaluate_submission, validate_submission
    from .storage import (
        authenticate_student,
        create_auth_token,
        create_test_session,
        get_challenges,
        get_student,
        get_student_by_token,
        get_student_stats,
        get_test_session,
        init_db,
        list_submissions_for_student,
        list_test_sessions_for_student,
        mark_test_session_submitted,
        register_student,
        save_submission,
        update_test_session_activity,
    )

app = Flask(__name__)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
CORS(
    app,
    resources={r"/api/*": {"origins": [item.strip() for item in allowed_origins.split(",") if item.strip()]}},
)
init_db(CHALLENGES)


def require_auth(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not auth_header.startswith(prefix):
            return jsonify({"error": "Authentication required"}), 401

        token = auth_header[len(prefix):].strip()
        student = get_student_by_token(token)
        if not student:
            return jsonify({"error": "Invalid or expired session"}), 401

        request.student = student
        request.auth_token = token
        return handler(*args, **kwargs)

    return wrapper


@app.get("/api/health")
def health_check():
    return jsonify({"status": "ok"})


@app.post("/api/auth/register")
def register():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "valid email is required"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    try:
        student = register_student(name=name, email=email, password=password)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    token = create_auth_token(student["id"])
    return jsonify({"student": student, "token": token, "stats": get_student_stats(student["id"])})


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    student = authenticate_student(email=email, password=password)
    if not student:
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_auth_token(student["id"])
    return jsonify({"student": student, "token": token, "stats": get_student_stats(student["id"])})


@app.get("/api/auth/me")
@require_auth
def auth_me():
    student = request.student
    return jsonify(
        {
            "student": student,
            "stats": get_student_stats(student["id"]),
            "sessions": list_test_sessions_for_student(student["id"]),
            "submissions": list_submissions_for_student(student["id"]),
        }
    )


@app.get("/api/challenges")
@require_auth
def list_challenges():
    return jsonify(get_challenges())


@app.post("/api/test-sessions")
@require_auth
def start_test_session():
    payload = request.get_json(silent=True) or {}
    challenge_id = (payload.get("challenge_id") or "").strip()
    if challenge_id not in CHALLENGES:
        return jsonify({"error": "Unknown challenge_id"}), 400

    session = create_test_session(request.student["id"], challenge_id)
    challenge = next(item for item in get_challenges() if item["id"] == challenge_id)
    return jsonify({"session": session, "challenge": challenge})


@app.post("/api/test-sessions/<int:session_id>/autosave")
@require_auth
def autosave_session(session_id):
    session = get_test_session(session_id)
    if not session or session["student_id"] != request.student["id"]:
        return jsonify({"error": "Test session not found"}), 404

    payload = request.get_json(silent=True) or {}
    latest_code = payload.get("code") or ""
    focus_warnings = int(payload.get("focus_warnings") or 0)
    fullscreen_exits = int(payload.get("fullscreen_exits") or 0)

    updated_session = update_test_session_activity(
        session_id=session_id,
        latest_code=latest_code,
        focus_warnings=focus_warnings,
        fullscreen_exits=fullscreen_exits,
    )
    return jsonify({"session": updated_session})


@app.post("/api/code/check")
@require_auth
def check_code():
    payload = request.get_json(silent=True) or {}
    challenge_id = (payload.get("challenge_id") or "").strip()
    code = payload.get("code") or ""

    if challenge_id not in CHALLENGES:
        return jsonify({"error": "Unknown challenge_id"}), 400
    if not code.strip():
        return jsonify({"error": "code is required"}), 400

    return jsonify(validate_submission(challenge_id, code))


@app.post("/api/submissions")
@require_auth
def submit_code():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("test_session_id")
    challenge_id = (payload.get("challenge_id") or "").strip()
    code = payload.get("code") or ""
    focus_warnings = int(payload.get("focus_warnings") or 0)
    fullscreen_exits = int(payload.get("fullscreen_exits") or 0)

    if not session_id:
        return jsonify({"error": "test_session_id is required"}), 400
    if challenge_id not in CHALLENGES:
        return jsonify({"error": "Unknown challenge_id"}), 400
    if not code.strip():
        return jsonify({"error": "code is required"}), 400

    session = get_test_session(int(session_id))
    if not session or session["student_id"] != request.student["id"]:
        return jsonify({"error": "Test session not found"}), 404

    result = evaluate_submission(challenge_id=challenge_id, code=code)
    saved_submission = save_submission(
        {
            "test_session_id": int(session_id),
            "student_id": request.student["id"],
            "challenge_id": challenge_id,
            "code": code,
            **result,
        }
    )
    updated_session = mark_test_session_submitted(
        session_id=int(session_id),
        latest_code=code,
        focus_warnings=focus_warnings,
        fullscreen_exits=fullscreen_exits,
    )
    return jsonify(
        {
            "student": get_student(request.student["id"]),
            "submission": saved_submission,
            "session": updated_session,
            "stats": get_student_stats(request.student["id"]),
            "history": list_submissions_for_student(request.student["id"]),
        }
    )


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
