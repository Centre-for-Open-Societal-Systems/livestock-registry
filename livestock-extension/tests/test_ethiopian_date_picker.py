from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "ui" / "staff-ui" / "overrides" / "src"
METADATA = (
    ROOT
    / "livestock-extension"
    / "src"
    / "openg2p_registry_livestock_extension"
    / "meta_data"
    / "zz-oan"
)


def test_staff_ui_registers_ethiopian_date_widgets():
    register = (UI / "oan" / "widgets" / "register.ts").read_text()

    assert "widget: 'date', component: DateOrVariant" in register
    assert "widget: ETHIOPIAN_DATE_CELL" in register
    assert (UI / "oan" / "widgets" / "EthiopianDateInputWidget.tsx").is_file()
    assert (
        UI / "features" / "activity" / "components" / "EthiopianDateInput.tsx"
    ).is_file()
    assert (
        UI / "features" / "activity" / "utils" / "ethiopianCalendar.ts"
    ).is_file()


def test_metadata_marks_form_and_table_dates_for_ethiopian_entry():
    migration = (METADATA / "47_ethiopian_dates.sql").read_text()

    assert "node->>'widget' IN ('date', 'oan-next-due-date')" in migration
    assert '"widget-variant": "ethiopian"' in migration
    assert "node ? 'column-key'" in migration
    assert '"widget": "oan-ethiopian-date-input"' in migration


def test_livestock_next_due_date_uses_ethiopian_input():
    widget = (UI / "oan" / "widgets" / "NextDueDateWidget.tsx").read_text()
    migration = (METADATA / "47_ethiopian_dates.sql").read_text()

    assert "EthiopianDateInputWidget" in widget
    assert "import { DateInputWidget" not in widget
    assert "<DateInputWidget" not in widget
    assert "'widget-variant': ETHIOPIAN_DATE_VARIANT" in widget
    assert "'oan-next-due-date'" in migration


def test_date_transform_runs_after_livestock_and_farmer_layouts():
    scripts = sorted(path.name for path in METADATA.glob("*.sql"))

    transform = scripts.index("47_ethiopian_dates.sql")
    assert transform > scripts.index("40_farmer_tab_layout.sql")
    assert transform > scripts.index("46_farmer_tab_full_profile.sql")
