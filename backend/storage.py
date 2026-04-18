import json
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "data"
SUBMISSIONS_FILE = DATA_DIR / "submissions.jsonl"


def save_submission(record):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    enriched_record = {
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        **record,
    }
    with SUBMISSIONS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enriched_record) + "\n")
