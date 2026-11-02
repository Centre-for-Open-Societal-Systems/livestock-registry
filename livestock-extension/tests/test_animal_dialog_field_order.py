"""The Livestock Details dialog asks Species and Breed before the Ear Tag
(G2R-229 point 18): a zz-oan patch reorders the animal table's columns."""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "openg2p_registry_livestock_extension" / "meta_data"
PATCH = ROOT / "register-metadata" / "zzzzzzzzz_animal_dialog_field_order.sql"


def test_species_and_breed_move_to_the_front_of_the_animal_table_only():
    sql = PATCH.read_text(encoding="utf-8")
    assert "node->>'widget-id' = 'ls_animal_details_table'" in sql
    assert re.search(r"WHEN 'species' THEN 0 WHEN 'breed' THEN 1 ELSE 2 END, position", sql)
    assert "WHERE section_id = 'livestock_animal_details_section_01'" in sql


def test_it_runs_after_the_files_that_rewrite_the_table_and_before_the_required_row_overlay():
    files = sorted(p.name for p in (ROOT / "register-metadata").glob("*.sql"))
    assert files.index(PATCH.name) > files.index("patch_ls_animal_details_sync_ui_schema.sql")
    assert files.index(PATCH.name) < files.index("zzzzzzzzzz_required_animal_row.sql")
