from flask import Flask, jsonify, request

from challenges import CHALLENGES, evaluate_submission
from storage import save_submission

app = Flask(__name__)


@app.get("/api/health")
def health_check():
    return jsonify({"status": "ok"})


@app.get("/api/challenges")
def list_challenges():
    items = []
    for challenge_id, challenge in CHALLENGES.items():
        items.append(
            {
                "id": challenge_id,
                "title": challenge["title"],
                "description": challenge["description"],
                "function_name": challenge["function_name"],
            }
        )
    return jsonify(items)


@app.post("/api/submissions")
def submit_code():
    payload = request.get_json(silent=True) or {}
    student_name = (payload.get("student_name") or "").strip()
    challenge_id = (payload.get("challenge_id") or "").strip()
    code = payload.get("code") or ""

    if not student_name:
        return jsonify({"error": "student_name is required"}), 400
    if challenge_id not in CHALLENGES:
        return jsonify({"error": "Unknown challenge_id"}), 400
    if not code.strip():
        return jsonify({"error": "code is required"}), 400

    result = evaluate_submission(challenge_id=challenge_id, code=code)
    record = {
        "student_name": student_name,
        "challenge_id": challenge_id,
        "code": code,
        **result,
    }
    save_submission(record)
    return jsonify(record)


if __name__ == "__main__":
    app.run(debug=True)
