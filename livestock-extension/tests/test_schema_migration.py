"""Add-only migration behavior on owned PostgreSQL schemas."""

import importlib
import os
import re
import unittest
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    Date,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy import (
    inspect as sa_inspect,
)
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.types import UserDefinedType

PACKAGE = os.environ.get(
    "REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension"
)
upgrade = importlib.import_module(PACKAGE + ".schema_migration")


@unittest.skipUnless(
    os.environ.get("FARMER_TEST_DATABASE_URL"), "Requires owned disposable PostgreSQL"
)
class AddOnlyMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.url = os.environ["FARMER_TEST_DATABASE_URL"]
        self.assertTrue(self.url.startswith("postgresql+asyncpg://"))
        self.schema = "oan_schema_test_" + uuid4().hex
        engine = create_async_engine(self.url)
        async with engine.begin() as conn:
            await conn.execute(text('CREATE SCHEMA "' + self.schema + '"'))
        await engine.dispose()
        self.engine = create_async_engine(
            self.url, execution_options={"schema_translate_map": {None: self.schema}}
        )

    async def asyncTearDown(self):
        await self.engine.dispose()
        assert re.fullmatch("oan_schema_test_[0-9a-f]{32}", self.schema)
        engine = create_async_engine(self.url)
        async with engine.begin() as conn:
            await conn.execute(text('DROP SCHEMA "' + self.schema + '" CASCADE'))
        await engine.dispose()

    async def columns(self, name):
        async with self.engine.connect() as conn:
            return await conn.run_sync(
                lambda sync: sa_inspect(sync).get_columns(name, schema=self.schema)
            )

    async def test_adds_missing_columns_once_preserving_existing_types_constraints_unknown_columns_and_rows(
        self,
    ):
        table = "quoted-table"
        old = Table(
            table,
            MetaData(),
            Column("id", Integer, primary_key=True),
            Column("old_text", String(12), nullable=False),
            Column("unknown_extra", JSON),
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(old.metadata.create_all)
            await conn.execute(
                old.insert().values(
                    id=1, old_text="Synthetic", unknown_extra={"preserve": True}
                )
            )
        mapped = Table(
            table,
            MetaData(),
            Column("id", Integer, primary_key=True),
            Column("old_text", Text),
            Column("new_date", Date),
            Column('new"json', JSON),
            Column("new_nonnull", Integer, nullable=False, default=0),
        )
        models = [SimpleNamespace(__table__=mapped)]
        added = await upgrade.add_missing_mapped_columns(self.engine, models)
        self.assertEqual(len(added), 3)
        self.assertEqual(
            await upgrade.add_missing_mapped_columns(self.engine, models), []
        )
        columns = {column["name"]: column for column in await self.columns(table)}
        self.assertEqual(columns["old_text"]["type"].length, 12)
        self.assertFalse(columns["old_text"]["nullable"])
        self.assertIn("unknown_extra", columns)
        async with self.engine.connect() as conn:
            row = (
                (
                    await conn.execute(
                        text('SELECT * FROM "' + self.schema + '"."quoted-table"')
                    )
                )
                .mappings()
                .one()
            )
            pk = await conn.run_sync(
                lambda sync: sa_inspect(sync).get_pk_constraint(
                    table, schema=self.schema
                )
            )
        self.assertEqual(row["old_text"], "Synthetic")
        self.assertEqual(row["unknown_extra"], {"preserve": True})
        self.assertIsNone(row["new_date"])
        self.assertIsNone(row['new"json'])
        self.assertIsNone(row["new_nonnull"])
        self.assertEqual(pk["constrained_columns"], ["id"])

    async def test_native_creation_still_owns_missing_tables(self):
        mapped = Table(
            "not-created", MetaData(), Column("id", Integer, primary_key=True)
        )
        self.assertEqual(
            await upgrade.add_missing_mapped_columns(
                self.engine, [SimpleNamespace(__table__=mapped)]
            ),
            [],
        )
        async with self.engine.connect() as conn:
            self.assertFalse(
                await conn.run_sync(
                    lambda sync: sa_inspect(sync).has_table(
                        "not-created", schema=self.schema
                    )
                )
            )

    async def test_failed_column_type_rolls_back_prior_adds_in_the_same_pass(self):
        class Unsupported(UserDefinedType):
            cache_ok = True

            def get_col_spec(self, **kwargs):
                return "OAN_UNSUPPORTED_TEST_TYPE"

        old = Table("atomic", MetaData(), Column("id", Integer, primary_key=True))
        async with self.engine.begin() as conn:
            await conn.run_sync(old.metadata.create_all)
        mapped = Table(
            "atomic",
            MetaData(),
            Column("id", Integer, primary_key=True),
            Column("first_new", Date),
            Column("unsupported", Unsupported()),
        )
        from sqlalchemy.exc import DBAPIError

        with self.assertRaises(DBAPIError):
            await upgrade.add_missing_mapped_columns(
                self.engine, [SimpleNamespace(__table__=mapped)]
            )
        self.assertEqual(
            [column["name"] for column in await self.columns("atomic")], ["id"]
        )


@unittest.skipUnless(
    os.environ.get("FARMER_TEST_DATABASE_URL"), "Requires owned disposable PostgreSQL"
)
class LegacyTableRenameTests(unittest.IsolatedAsyncioTestCase):
    """The Farmer-reference tables move to their new names once, with their data."""

    async def asyncSetUp(self):
        self.url = os.environ["FARMER_TEST_DATABASE_URL"]
        self.schema = "oan_schema_test_" + uuid4().hex
        engine = create_async_engine(self.url)
        async with engine.begin() as conn:
            await conn.execute(text('CREATE SCHEMA "' + self.schema + '"'))
        await engine.dispose()
        self.engine = create_async_engine(
            self.url, execution_options={"schema_translate_map": {None: self.schema}}
        )
        async with self.engine.begin() as conn:
            schema = '"' + self.schema + '"'
            await conn.exec_driver_sql(
                f"CREATE TABLE {schema}.coss_farmer_references (reference_id varchar PRIMARY KEY, uid varchar UNIQUE)"
            )
            await conn.exec_driver_sql(
                f"CREATE TABLE {schema}.coss_farmer_reference_requests (request_id varchar PRIMARY KEY, "
                f"reference_id varchar NOT NULL REFERENCES {schema}.coss_farmer_references (reference_id))"
            )
            await conn.exec_driver_sql(
                f"CREATE INDEX ix_coss_farmer_reference_requests_reference_id ON {schema}.coss_farmer_reference_requests (reference_id)"
            )
            await conn.exec_driver_sql(
                f"CREATE TABLE {schema}.coss_farmer_workflow_outbox (id serial PRIMARY KEY, state varchar)"
            )
            await conn.exec_driver_sql(
                f"INSERT INTO {schema}.coss_farmer_references VALUES ('r1', 'u1')"
            )
            await conn.exec_driver_sql(
                f"INSERT INTO {schema}.coss_farmer_workflow_outbox (state) VALUES ('PENDING')"
            )

    async def asyncTearDown(self):
        await self.engine.dispose()
        assert re.fullmatch("oan_schema_test_[0-9a-f]{32}", self.schema)
        engine = create_async_engine(self.url)
        async with engine.begin() as conn:
            await conn.execute(text('DROP SCHEMA "' + self.schema + '" CASCADE'))
        await engine.dispose()

    async def names(self, kind):
        queries = {
            "tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = :s",
            "indexes": "SELECT indexname FROM pg_indexes WHERE schemaname = :s",
            "constraints": "SELECT conname FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = :s",
            "sequences": "SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = :s",
        }
        async with self.engine.connect() as conn:
            rows = await conn.execute(text(queries[kind]), {"s": self.schema})
            return {row[0] for row in rows}

    async def test_renames_tables_with_their_indexes_constraints_sequences_and_rows_and_is_idempotent(self):
        first = await upgrade.rename_legacy_tables(self.engine)
        self.assertEqual(
            sorted(new for _, new in first),
            ["g2p_farmer_reference_awe_outbox", "g2p_farmer_reference_requests", "g2p_farmer_references"],
        )
        self.assertEqual(await upgrade.rename_legacy_tables(self.engine), [])
        for kind in ("tables", "indexes", "constraints", "sequences"):
            with self.subTest(kind=kind):
                self.assertFalse([name for name in await self.names(kind) if name.startswith(("coss_", "ix_coss_"))])
        self.assertIn("ix_g2p_farmer_reference_requests_reference_id", await self.names("indexes"))
        self.assertIn("g2p_farmer_reference_awe_outbox_id_seq", await self.names("sequences"))
        async with self.engine.connect() as conn:
            schema = '"' + self.schema + '"'
            self.assertEqual((await conn.exec_driver_sql(f"SELECT uid FROM {schema}.g2p_farmer_references")).scalar_one(), "u1")
            self.assertEqual((await conn.exec_driver_sql(f"SELECT state FROM {schema}.g2p_farmer_reference_awe_outbox")).scalar_one(), "PENDING")

    async def test_a_database_without_the_old_tables_is_left_alone(self):
        await upgrade.rename_legacy_tables(self.engine)
        before = await self.names("tables")
        await upgrade.rename_legacy_tables(self.engine)
        self.assertEqual(await self.names("tables"), before)

    async def test_an_existing_new_table_is_never_replaced(self):
        async with self.engine.begin() as conn:
            await conn.exec_driver_sql(f'CREATE TABLE "{self.schema}".g2p_farmer_references (reference_id varchar PRIMARY KEY)')
        await upgrade.rename_legacy_tables(self.engine)
        names = await self.names("tables")
        self.assertIn("coss_farmer_references", names)
        self.assertIn("g2p_farmer_references", names)
