"""Verify a legacy schema matches ORM metadata before stamping Alembic head.

This is an explicit one-time deployment operation. It never creates or alters
application tables and refuses to stamp when any modeled table or column is
missing.
"""

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

import app.models  # noqa: F401
from app.database import engine
from app.models.base import Base


def main() -> None:
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables)

    missing_tables = sorted(expected_tables - actual_tables)
    missing_columns: list[str] = []
    for table_name in sorted(expected_tables & actual_tables):
        actual_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        expected_columns = set(Base.metadata.tables[table_name].columns.keys())
        missing_columns.extend(
            f"{table_name}.{column}"
            for column in sorted(expected_columns - actual_columns)
        )

    if missing_tables or missing_columns:
        details = []
        if missing_tables:
            details.append("missing tables: " + ", ".join(missing_tables))
        if missing_columns:
            details.append("missing columns: " + ", ".join(missing_columns))
        raise RuntimeError(
            "Legacy schema does not match the model baseline; refusing to "
            "stamp Alembic. " + "; ".join(details)
        )

    config = Config("alembic.ini")
    # Existing pre-Alembic installations correspond to the last legacy release.
    # Stamp only that boundary so the explicit normalization revision still runs.
    command.stamp(config, "73be620df811")
    command.upgrade(config, "head")
    command.check(config)
    print(
        "Verified and normalized the legacy schema; Alembic head and ORM parity confirmed."
    )


if __name__ == "__main__":
    main()
