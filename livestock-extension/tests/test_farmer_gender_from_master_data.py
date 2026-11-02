"""The Farmer identity section's Gender dropdown reads the Master Data GENDER
list, like every other coded field (the farmer registry uses the same list)."""

import pathlib
import re

import pytest

META = pathlib.Path(__file__).resolve().parents[1] / "src" / "openg2p_registry_livestock_extension" / "meta_data"
GENDER_PATH = "f9c6a359-9563-5a43-b0fe-6c7e452037a3.gender"


@pytest.mark.parametrize("name", ["register-metadata/g2p_register_sections.sql", "zz-oan/40_farmer_tab_layout.sql"])
def test_farmer_gender_is_the_master_data_gender_list(name):
    text = (META / name).read_text(encoding="utf-8")
    compact = re.sub(r"\s+", "", text)
    widgets = [m.start() for m in re.finditer(re.escape(f'"widget-data-path":"{GENDER_PATH}"'), compact)]
    assert widgets, f"no farmer gender widget in {name}"
    for start in widgets:
        source = compact[start:start + 400]
        assert '"type":"api"' in source and '"attribute_id":"GENDER"' in source and '"valueKey":"value_code"' in source
        assert '"type":"static"' not in source.split('"widget-data-source"', 1)[1][:30]
