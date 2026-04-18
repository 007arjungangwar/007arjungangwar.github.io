import json
import subprocess
import sys
from pathlib import Path
import tempfile


CHALLENGES = {
    "sum-two-numbers": {
        "title": "Sum Two Numbers",
        "description": "Write solve(a, b) and return the sum of both integers.",
        "function_name": "solve",
        "tests": [
            {"input": [1, 2], "expected": 3},
            {"input": [-5, 9], "expected": 4},
            {"input": [100, 250], "expected": 350},
        ],
    },
    "reverse-string": {
        "title": "Reverse A String",
        "description": "Write solve(text) and return the reversed string.",
        "function_name": "solve",
        "tests": [
            {"input": ["python"], "expected": "nohtyp"},
            {"input": ["Arjun"], "expected": "nujrA"},
            {"input": ["12345"], "expected": "54321"},
        ],
    },
}


RUNNER_TEMPLATE = """
import importlib.util
import json
import sys

module_path = sys.argv[1]
function_name = sys.argv[2]
raw_args = sys.argv[3]

spec = importlib.util.spec_from_file_location("student_submission", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if not hasattr(module, function_name):
    raise AttributeError(f"Expected function '{{function_name}}' was not found.")

function = getattr(module, function_name)
args = json.loads(raw_args)
result = function(*args)
print(json.dumps({"result": result}))
"""


def evaluate_submission(challenge_id, code):
    challenge = CHALLENGES[challenge_id]
    tests = challenge["tests"]
    function_name = challenge["function_name"]
    results = []
    temp_root = Path(__file__).resolve().parent / ".judge_tmp"
    temp_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
        temp_path = Path(temp_dir)
        submission_path = temp_path / "submission.py"
        runner_path = temp_path / "runner.py"

        submission_path.write_text(code, encoding="utf-8")
        runner_path.write_text(RUNNER_TEMPLATE, encoding="utf-8")

        for test in tests:
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        str(runner_path),
                        str(submission_path),
                        function_name,
                        json.dumps(test["input"]),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    cwd=temp_dir,
                )
            except subprocess.TimeoutExpired:
                results.append(
                    {
                        "input": test["input"],
                        "expected": test["expected"],
                        "passed": False,
                        "error": "Time limit exceeded",
                    }
                )
                continue

            if completed.returncode != 0:
                results.append(
                    {
                        "input": test["input"],
                        "expected": test["expected"],
                        "passed": False,
                        "error": completed.stderr.strip() or "Execution failed",
                    }
                )
                continue

            payload = json.loads(completed.stdout.strip())
            actual = payload["result"]
            results.append(
                {
                    "input": test["input"],
                    "expected": test["expected"],
                    "actual": actual,
                    "passed": actual == test["expected"],
                }
            )

    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    return {
        "status": "accepted" if passed == total else "failed",
        "passed_tests": passed,
        "total_tests": total,
        "results": results,
    }
