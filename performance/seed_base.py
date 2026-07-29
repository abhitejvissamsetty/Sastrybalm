"""Seed the minimal deterministic hierarchy required by the release load gate."""

from pathlib import Path
import sys

from app.database import SessionLocal
from app.models.user import User, UserRole

TESTS = Path(__file__).resolve().parents[1] / "tests"
sys.path.insert(0, str(TESTS))
from factories import acceptance_environment  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        exists = db.query(User.id).filter(User.role == UserRole.field_rep).first()
        if not exists:
            acceptance_environment(db)
        print("performance-base-fixtures-ready")
    finally:
        db.close()


if __name__ == "__main__":
    main()
