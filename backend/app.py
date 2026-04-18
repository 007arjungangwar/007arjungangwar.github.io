from flask import Flask, jsonify, request
from flask_cors import CORS

from challenges import CHALLENGES, evaluate_submission
from storage import (
    get_challenges,
    get_student,
    get_student_stats,
    init_db,
    list_submissions_for_student,
    save_submission,
    upsert_student,
)

app = Flask(__name__)
CORS(app)
init_db(CHALLENGES)


@app.get("/api/health")
def health_check():
    return jsonify({"status": "ok"})


@app.get("/api/challenges")
def list_challenges():
    return jsonify(get_challenges())


@app.post("/api/students/login")
def login_student():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "valid email is required"}), 400

    student = upsert_student(name=name, email=email)
    stats = get_student_stats(student["id"])
    return jsonify({"student": student, "stats": stats})


@app.get("/api/students/<int:student_id>")
def fetch_student(student_id):
    student = get_student(student_id)
    if not student:
        return jsonify({"error": "student not found"}), 404
    return jsonify({"student": student, "stats": get_student_stats(student_id)})


@app.get("/api/students/<int:student_id>/submissions")
def fetch_student_submissions(student_id):
    student = get_student(student_id)
    if not student:
        return jsonify({"error": "student not found"}), 404
    return jsonify(
        {
            "student": student,
            "stats": get_student_stats(student_id),
            "submissions": list_submissions_for_student(student_id),
        }
    )


@app.post("/api/submissions")
def submit_code():
    payload = request.get_json(silent=True) or {}
    student_id = payload.get("student_id")
    challenge_id = (payload.get("challenge_id") or "").strip()
    code = payload.get("code") or ""

    if not student_id:
        return jsonify({"error": "student_id is required"}), 400
    student = get_student(int(student_id))
    if not student:
        return jsonify({"error": "student not found"}), 404
    if challenge_id not in CHALLENGES:
        return jsonify({"error": "Unknown challenge_id"}), 400
    if not code.strip():
        return jsonify({"error": "code is required"}), 400

    result = evaluate_submission(challenge_id=challenge_id, code=code)
    record = save_submission(
        {
            "student_id": int(student_id),
            "challenge_id": challenge_id,
            "code": code,
            **result,
        }
    )
    return jsonify(
        {
            "student": student,
            "submission": record,
            "stats": get_student_stats(int(student_id)),
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
