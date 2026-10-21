"""Add the columns a model has and its table lacks.

``create_migrate()`` is ``metadata.create_all``: it creates a missing table and
leaves an existing one as it is. A database first created on an older
registry-platform therefore keeps the column set of that release, and a
column the platform added later (for example ``subject_internal_record_id``
on every register history table, which 1.2 writes on each register ingest)
makes every insert into that table fail.

``add_missing_columns`` compares each table with its model and adds what is
missing. It only adds: it never drops, renames or retypes a column. A column
that is NOT NULL and has no server default cannot be added to a table that
already has rows, so it is reported and left for a hand-written migration.
"""

import logging

from sqlalchemy import inspect, text

_logger = logging.getLogger(__name__)


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _add_to_table(sync_conn, table) -> list[str]:
    inspector = inspect(sync_conn)
    if not inspector.has_table(table.name):
        return []
    existing = {column["name"] for column in inspector.get_columns(table.name)}
    added = []
    for column in table.columns:
        if column.name in existing:
            continue
        if not column.nullable and column.server_default is None:
            _logger.warning(
                "Schema sync: %s.%s is NOT NULL without a server default; not added",
                table.name, column.name,
            )
            continue
        column_type = column.type.compile(dialect=sync_conn.dialect)
        default = ""
        if column.server_default is not None and hasattr(column.server_default, "arg"):
            arg = column.server_default.arg
            default = f" DEFAULT {arg.text if hasattr(arg, 'text') else arg}"
        sync_conn.execute(text(
            f"ALTER TABLE {_quote(table.name)} ADD COLUMN IF NOT EXISTS "
            f"{_quote(column.name)} {column_type}{default}"
        ))
        if column.index:
            sync_conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {_quote(f'ix_{table.name}_{column.name}')} "
                f"ON {_quote(table.name)} ({_quote(column.name)})"
            ))
        added.append(f"{table.name}.{column.name}")
    return added


async def add_missing_columns(engine, models) -> list[str]:
    """Add the missing nullable columns of ``models`` (ORM classes) and return them."""
    added: list[str] = []
    async with engine.begin() as conn:
        for model in models:
            added.extend(await conn.run_sync(_add_to_table, model.__table__))
    for name in added:
        _logger.warning("Schema sync: added column %s", name)
    if not added:
        _logger.info("Schema sync: every livestock table has all its columns")
    return added
