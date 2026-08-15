"""Adds columns that exist in the models but not yet in the database.

`Base.metadata.create_all()` creates missing *tables* but never alters existing ones,
so a dev database built before a new column was added silently lacks it. This walks
the model metadata and issues `ALTER TABLE ... ADD COLUMN` for anything missing.

Development convenience only — production uses Alembic (`alembic upgrade head`).
Deliberately limited to additive changes: it never drops, renames or retypes.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

from app.models import Base

logger = logging.getLogger("hrms.schema")


def _default_clause(column) -> str:
    """A literal DEFAULT so existing rows get a sane value for NOT NULL columns."""
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return ""
    value = default.arg
    if isinstance(value, bool):
        return f" DEFAULT {1 if value else 0}"
    if isinstance(value, (int, float)):
        return f" DEFAULT {value}"
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f" DEFAULT '{escaped}'"
    return ""


def sync_schema(engine: Engine) -> list[str]:
    """Returns the list of `table.column` additions that were applied."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    applied: list[str] = []

    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all() handles brand-new tables

            present = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue

                spec = CreateColumn(column).compile(engine).string
                # SQLite cannot add a NOT NULL column without a default; give it one
                # or relax the constraint for the backfill.
                if not column.nullable and not _default_clause(column):
                    spec = spec.replace(" NOT NULL", "")
                spec += _default_clause(column)

                connection.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {spec}"))
                applied.append(f"{table.name}.{column.name}")

    if applied:
        logger.info("Schema sync added %d column(s): %s", len(applied), ", ".join(applied))
    return applied
