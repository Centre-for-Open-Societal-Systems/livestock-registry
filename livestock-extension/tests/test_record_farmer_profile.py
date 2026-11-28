"""The farmer's personal details on the livestock record: copied from the approved Farmer, never
cleared, and refreshed on every active record of a Farmer when a change to it is approved."""
import datetime
import importlib
import json
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import Boolean, Date, String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
projection = importlib.import_module(PACKAGE + ".farmer_reference.projection")
SOURCE = Path(__file__).resolve().parents[1] / "src/openg2p_registry_livestock_extension"
OVERLAY = SOURCE / "meta_data/site-configuration/96_record_farmer_profile.sql"
LIVESTOCK_REGISTER = "997676d3-7008-59f9-b23e-613ad79bbb08"


class Base(DeclarativeBase):
    pass


class Farmer(Base):
    __tablename__ = "farmers"
    internal_record_id: Mapped[str] = mapped_column(String, primary_key=True)
    farmer_id: Mapped[str] = mapped_column(String)
    fayda_fan_id: Mapped[str] = mapped_column(String)
    record_status: Mapped[str] = mapped_column(String)
    first_name: Mapped[str] = mapped_column(String, nullable=True)
    middle_name: Mapped[str] = mapped_column(String, nullable=True)
    last_name: Mapped[str] = mapped_column(String, nullable=True)
    gender: Mapped[str] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[datetime.date] = mapped_column(Date, nullable=True)
    mobile_number: Mapped[str] = mapped_column(String, nullable=True)
    marital_status: Mapped[str] = mapped_column(String, nullable=True)
    education_level: Mapped[str] = mapped_column(String, nullable=True)
    language_spoken: Mapped[str] = mapped_column(String, nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=True)
    disability_type: Mapped[str] = mapped_column(String, nullable=True)


class Record(Base):
    __tablename__ = "records"
    internal_record_id: Mapped[str] = mapped_column(String, primary_key=True)
    farmer_uuid: Mapped[str] = mapped_column(String, nullable=True)
    farmer_id: Mapped[str] = mapped_column(String, nullable=True)
    fayda_fan_id: Mapped[str] = mapped_column(String, nullable=True)
    link_foundational_id: Mapped[str] = mapped_column(String, nullable=True)
    farmer_name: Mapped[str] = mapped_column(String, nullable=True)
    record_status: Mapped[str] = mapped_column(String)
    search_text: Mapped[str] = mapped_column(String, nullable=True)
    record_name: Mapped[str] = mapped_column(String, nullable=True)
    farmer_gender: Mapped[str] = mapped_column(String, nullable=True)
    farmer_date_of_birth: Mapped[datetime.date] = mapped_column(Date, nullable=True)
    farmer_mobile_number: Mapped[str] = mapped_column(String, nullable=True)
    farmer_marital_status: Mapped[str] = mapped_column(String, nullable=True)
    farmer_education_level: Mapped[str] = mapped_column(String, nullable=True)
    farmer_language_spoken: Mapped[str] = mapped_column(String, nullable=True)
    farmer_disabled: Mapped[bool] = mapped_column(Boolean, nullable=True)
    farmer_disability_type: Mapped[str] = mapped_column(String, nullable=True)

    def get_search_text_fields(self):
        return f"{self.farmer_name} {self.farmer_id}"

    def get_record_name_fields(self):
        return self.farmer_name


def test_profile_is_copied_and_never_cleared():
    row = SimpleNamespace(**dict.fromkeys(projection.MIRRORED_PROFILE_FIELDS.values()))
    source = SimpleNamespace(gender="FEMALE", date_of_birth=datetime.date(1980, 5, 1), mobile_number="+251911000001",
                             marital_status="MARRIED", education_level="PRIMARY", language_spoken="Afaan Oromo",
                             disabled=False, disability_type=None)
    assert projection._mirror_profile(row, source) is True
    assert (row.farmer_gender, row.farmer_disabled, row.farmer_disability_type) == ("FEMALE", False, None)
    assert projection._mirror_profile(row, source) is False  # nothing left to change
    # A Farmer without a value (None or empty) leaves the record's value.
    blank = SimpleNamespace(**dict.fromkeys(projection.MIRRORED_PROFILE_FIELDS, None))
    blank.mobile_number = ""
    assert projection._mirror_profile(row, blank) is False
    assert row.farmer_mobile_number == "+251911000001"


def test_a_record_without_the_columns_is_left_alone():
    row = SimpleNamespace(farmer_id="FR-1")
    assert projection._mirror_profile(row, SimpleNamespace(gender="MALE")) is False
    assert not hasattr(row, "farmer_gender")


class FanOutTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite://")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        pair = {"farmer_id": "FR-000000000001", "fayda_fan_id": "0000000000000001"}
        async with self.sessions.begin() as session:
            session.add_all([
                Farmer(internal_record_id="local-1", record_status="ACTIVE", first_name="Abebe", last_name="Kebede",
                       gender="MALE", marital_status="SINGLE", mobile_number="+251911000001", **pair),
                Record(internal_record_id="active-1", farmer_uuid="local-1", farmer_name="Abebe Kebede",
                       record_status="ACTIVE", **pair),
                Record(internal_record_id="active-2", farmer_uuid="local-1", farmer_name="Abebe Kebede",
                       record_status="ACTIVE", farmer_marital_status="SINGLE", **pair),
                Record(internal_record_id="inactive", farmer_uuid="local-1", record_status="INACTIVE", **pair),
                Record(internal_record_id="other-farmer", farmer_uuid="local-2", record_status="ACTIVE", **pair),
                # Linked to this Farmer but under another Farmer ID: left as it is, not an error.
                Record(internal_record_id="mismatch", farmer_uuid="local-1", farmer_id="FR-000000000009",
                       fayda_fan_id="0000000000000001", record_status="ACTIVE"),
            ])

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_an_approved_change_reaches_every_active_record_of_the_farmer(self):
        async with self.sessions.begin() as session:
            farmer = await session.get(Farmer, "local-1")
            farmer.marital_status = "MARRIED"
            farmer.last_name = "Tadesse"
            with self.assertLogs("oan-farmer-reference-projection", "WARNING") as logged:
                self.assertEqual(await projection.refresh_linked_records(session, farmer, Record), 2)
            self.assertIn("mismatch", logged.output[0])
        async with self.sessions() as session:
            for record_id in ("active-1", "active-2"):
                row = await session.get(Record, record_id)
                self.assertEqual((row.farmer_marital_status, row.farmer_gender, row.farmer_name),
                                 ("MARRIED", "MALE", "Abebe Tadesse"))
                self.assertEqual(row.record_name, "Abebe Tadesse")
            for record_id in ("inactive", "other-farmer", "mismatch"):
                row = await session.get(Record, record_id)
                self.assertIsNone(row.farmer_marital_status)

    async def test_a_second_refresh_changes_nothing(self):
        async with self.sessions.begin() as session:
            farmer = await session.get(Farmer, "local-1")
            await projection.refresh_linked_records(session, farmer, Record)
        async with self.sessions.begin() as session:
            farmer = await session.get(Farmer, "local-1")
            with self.assertLogs("oan-farmer-reference-projection", "WARNING"):
                self.assertEqual(await projection.refresh_linked_records(session, farmer, Record), 0)


def test_approval_of_a_farmer_update_refreshes_the_records():
    native = (SOURCE / "farmer_reference/native.py").read_text(encoding="utf-8")
    body = native[native.index("    async def approve_register(self, change_request, section, session):"):]
    body = body[:body.index("\nclass ")]
    assert 'if request.action == "UPDATE":' in body
    assert body.index("await super().approve_register(change_request, section, session)") < \
        body.index("await refresh_dependent_records(session, reference.local_farmer_id)")
    assert '"G2PRegisterLivestock"' in native


def test_the_first_tab_shows_the_mirrored_details_read_only():
    sql = OVERLAY.read_text(encoding="utf-8")
    schema = json.loads(re.search(r"^'(\{.*\})'::jsonb,$", sql, re.M).group(1).replace("''", "'"))
    assert schema["section-editable"] is False
    widgets = [w for outer in schema["panels"] for inner in outer["panels"] for w in inner["widgets"]]
    assert all(w["widget-readonly"] for w in widgets)
    paths = {w["widget-data-path"] for w in widgets}
    assert paths == {f"{LIVESTOCK_REGISTER}.{column}" for column in projection.MIRRORED_PROFILE_FIELDS.values()}
    assert "'livestock_livestock_tab','livestock_livestock_farmer_profile_section_04',15)" in sql
    assert "identity" not in schema["section-id"]


def test_every_mirrored_column_is_on_the_livestock_record():
    model = (SOURCE / "register_domain/models/livestock.py").read_text(encoding="utf-8")
    for column in projection.MIRRORED_PROFILE_FIELDS.values():
        assert re.search(rf"^    {column}: Mapped\[", model, re.M), column

class DeployFillTests(FanOutTests):
    """fill_empty_profiles: run by the staff-api migrate command on every deploy."""

    async def test_the_deploy_fill_writes_only_empty_values_of_active_records(self):
        async with self.sessions.begin() as session:
            # A value the record already holds is never overwritten by the deploy fill.
            (await session.get(Record, "active-2")).farmer_gender = "FEMALE"
        filled = await projection.fill_empty_profiles(self.engine, "farmers", "records")
        async with self.sessions() as session:
            one, two = await session.get(Record, "active-1"), await session.get(Record, "active-2")
            self.assertEqual((one.farmer_gender, one.farmer_marital_status, one.farmer_mobile_number),
                             ("MALE", "SINGLE", "+251911000001"))
            self.assertEqual((two.farmer_gender, two.farmer_marital_status, two.farmer_mobile_number),
                             ("FEMALE", "SINGLE", "+251911000001"))
            # Not active, no Farmer here, or under another Farmer ID: left as they are.
            for left in ("inactive", "other-farmer", "mismatch"):
                self.assertIsNone((await session.get(Record, left)).farmer_gender, left)
            # A Farmer without a value fills nothing.
            self.assertIsNone(one.farmer_education_level)
        # active-1: gender, marital status, mobile; active-2: mobile only.
        self.assertEqual(filled, 4)

    async def test_a_second_deploy_fill_changes_nothing(self):
        await projection.fill_empty_profiles(self.engine, "farmers", "records")
        self.assertEqual(await projection.fill_empty_profiles(self.engine, "farmers", "records"), 0)

    async def test_an_empty_string_counts_as_empty(self):
        async with self.sessions.begin() as session:
            (await session.get(Record, "active-1")).farmer_gender = ""
        await projection.fill_empty_profiles(self.engine, "farmers", "records")
        async with self.sessions() as session:
            self.assertEqual((await session.get(Record, "active-1")).farmer_gender, "MALE")


def test_migrate_runs_the_deploy_fill():
    app = (SOURCE / "app.py").read_text(encoding="utf-8")
    migrate = app[app.index("def migrate_database"):]
    assert migrate.index("migrate_existing_schema(dbengine.get())") < migrate.index("await fill_empty_profiles(")
