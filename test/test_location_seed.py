import json
import re
from pathlib import Path


def test_canonical_location_section_includes_one_map():
    repo = Path(__file__).resolve().parents[1]
    (metadata,) = repo.glob('*-extension/src/*/meta_data/register-metadata')
    domain = metadata.parents[3].name.removesuffix('-extension')
    sections = (metadata / 'g2p_register_sections.sql').read_text(encoding='utf-8')
    (section_row,) = [row for row in sections.splitlines() if f"'{domain}_{domain}_location_section_03'" in row]
    schema = json.loads(re.search(r"'(\{.*\})'", section_row)[1])
    (panel,) = [panel for panel in schema['panels'] if panel.get('panel-id') == 'location_widgets']
    (widget,) = panel['widgets']
    assert widget['widget'] == 'oan-geo-point'
    assert 'geo-hierarchy' in section_row

    if domain == 'livestock':
        sync = (metadata / 'patch_ls_livestock_location_sync_ui_schema.sql').read_text(encoding='utf-8')
        assert json.loads(re.search(r"'(\{.*\})'", sync)[1]) == schema
