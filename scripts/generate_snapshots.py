import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.analysis_service import generate_snapshot
from app.analyzers.skill_extractor import extract_and_link_skills
from app.database import SessionLocal


def main():
    print("Generating daily snapshot...")
    snapshot = generate_snapshot()
    print(f"Done. Active jobs: {snapshot.total_active}")

    print("Extracting skills...")
    db = SessionLocal()
    try:
        count = extract_and_link_skills(db)
        print(f"Linked {count} job-skill associations.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
