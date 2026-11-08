"""Add mapped extension columns after native table creation, without data repair.

Existing columns, types, defaults, constraints and unknown user columns remain
untouched. New columns use their mapped SQL type and stay nullable on old tables;
new tables retain the complete native model definition through create_migrate.
"""

import logging
from collections.abc import Iterable

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

_logger = logging.getLogger("oan-registry-schema")


async def add_missing_mapped_columns(
    engine: AsyncEngine, model_classes: Iterable[type]
) -> list[tuple[str, str]]:
    tables = {model.__table__.key: model.__table__ for model in model_classes}
    schema_map = (
        engine.sync_engine.get_execution_options().get("schema_translate_map") or {}
    )
    added = []
    async with engine.begin() as connection:
        for table in sorted(tables.values(), key=lambda item: item.key):
            schema = schema_map.get(table.schema, table.schema)

            def present_columns(sync_connection, name=table.name, target_schema=schema):
                inspector = sa_inspect(sync_connection)
                if not inspector.has_table(name, schema=target_schema):
                    return None
                return {
                    column["name"]
                    for column in inspector.get_columns(name, schema=target_schema)
                }

            present = await connection.run_sync(present_columns)
            if present is None:
                # Native create_migrate owns missing tables, not this pass.
                _logger.debug(
                    "Mapped table not present for add-only pass: %s", table.key
                )
                continue
            quote = connection.dialect.identifier_preparer
            table_name = quote.quote(table.name)
            if schema:
                table_name = quote.quote_schema(schema) + "." + table_name
            for column in table.columns:
                if column.name in present:
                    continue
                column_type = column.type.compile(dialect=connection.dialect)
                _logger.debug("Adding mapped column %s.%s", table.key, column.name)
                await connection.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {quote.quote(column.name)} {column_type}"
                    )
                )
                present.add(column.name)
                added.append((table.key, column.name))
    return added


# Tables the Farmer-reference ledger created under their former names. The new
# code maps the new names, so the rename must run before native table creation;
# otherwise an empty table would be created next to the one holding the data.
LEGACY_TABLE_RENAMES = (
    ("coss_farmer_references", "g2p_farmer_references"),
    ("coss_farmer_reference_requests", "g2p_farmer_reference_requests"),
    ("coss_farmer_submission_dependencies", "g2p_farmer_submission_dependencies"),
    ("coss_farmer_workflow_outbox", "g2p_farmer_reference_awe_outbox"),
    ("coss_farmer_pending_lookups", "g2p_farmer_pending_lookups"),
    ("coss_approval_binding_archive", "g2p_approval_binding_archive"),
)


async def rename_legacy_tables(
    engine: AsyncEngine, renames: Iterable[tuple[str, str]] = LEGACY_TABLE_RENAMES
) -> list[tuple[str, str]]:
    """Rename each old table to its new name, with its indexes, constraints and sequences.

    Idempotent: a table is renamed only when the old name exists and the new one
    does not, so a second run (or a fresh database) changes nothing. Inverse for
    rollback: ALTER TABLE <new> RENAME TO <old> for each pair, plus the same
    replacement of the old table name inside the index and constraint names.
    """
    schema_map = (
        engine.sync_engine.get_execution_options().get("schema_translate_map") or {}
    )
    schema = schema_map.get(None)
    renamed = []

    def run(sync_connection):
        inspector = sa_inspect(sync_connection)
        quote = sync_connection.dialect.identifier_preparer

        def qualified(name):
            return (quote.quote_schema(schema) + "." if schema else "") + quote.quote(name)

        def execute(statement):
            sync_connection.exec_driver_sql(statement)

        for old, new in renames:
            if not inspector.has_table(old, schema=schema):
                continue
            if inspector.has_table(new, schema=schema):
                _logger.warning(
                    "Both %s and %s exist; %s is left as it is", old, new, old
                )
                continue
            execute(f"ALTER TABLE {qualified(old)} RENAME TO {quote.quote(new)}")
            regclass = qualified(new).replace("'", "''")
            constraints = [
                row[0]
                for row in sync_connection.exec_driver_sql(
                    "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass"
                    % ("'" + regclass + "'")
                )
            ]
            # A primary key or unique constraint owns the index of the same name.
            for name in constraints:
                if old in name:
                    execute(
                        f"ALTER TABLE {qualified(new)} RENAME CONSTRAINT {quote.quote(name)} "
                        f"TO {quote.quote(name.replace(old, new))}"
                    )
            indexes = [
                row[0]
                for row in sync_connection.exec_driver_sql(
                    "SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                    "WHERE i.indrelid = %s::regclass" % ("'" + regclass + "'")
                )
            ]
            for name in indexes:
                if old in name:
                    target = (quote.quote_schema(schema) + "." if schema else "") + quote.quote(name)
                    execute(f"ALTER INDEX {target} RENAME TO {quote.quote(name.replace(old, new))}")
            sequences = [
                row[0]
                for row in sync_connection.exec_driver_sql(
                    "SELECT s.relname FROM pg_class s JOIN pg_depend d ON d.objid = s.oid "
                    "AND d.deptype IN ('a', 'i') WHERE s.relkind = 'S' AND d.refobjid = %s::regclass"
                    % ("'" + regclass + "'")
                )
            ]
            for name in sequences:
                if old in name:
                    target = (quote.quote_schema(schema) + "." if schema else "") + quote.quote(name)
                    execute(f"ALTER SEQUENCE {target} RENAME TO {quote.quote(name.replace(old, new))}")
            renamed.append((old, new))
        return renamed

    async with engine.begin() as connection:
        await connection.run_sync(run)
    return renamed
