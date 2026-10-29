"""Form v5 submissions carry Master Data geo unit ids (P-codes) and the record
gets the hierarchy document the staff portal's geo-hierarchy widget reads."""
import importlib
import json
import os
from pathlib import Path

import pytest
from jinja2 import Environment

PACKAGE = os.environ.get('REGISTRY_EXTENSION_MODULE', 'openg2p_registry_livestock_extension')
ROOT = Path(importlib.import_module(PACKAGE).__file__).parent

pytestmark = pytest.mark.skipif('livestock' not in PACKAGE, reason='livestock transform')


def render(location):
    data = {'farmer': {'farmer_id': 'FR-000000000001', 'fayda_id': '001234567890'},
            'location': location,
            'livestock': [{'species_id': 'cattle', 'breed': 'local', 'gender': 'female',
                           'primary_identifier': 'ANIMAL-001', 'date_of_birth': '2020-01-01'}]}
    template = (ROOT / 'templates' / 'odk_to_livestock_intake.j2').read_text(encoding='utf-8')
    return json.loads(Environment().from_string(template).render(expanded=data))


def test_v5_location_is_pcodes_with_hierarchy():
    row = render({'location_source': 'mds', 'region_code': 'ET04', 'zone_code': 'ET0404',
                  'woreda_code': 'ET040404', 'kebele_code': 'ET040404888003'})['ls_livestock_location'][0]
    assert (row['region_id'], row['zone_id'], row['woreda_id'], row['kebele_id']) == (
        'ET04', 'ET0404', 'ET040404', 'ET040404888003')
    assert row['geo_lowest_level_value_id'] == 'ET040404888003'
    assert row['region'] is None and row['kebele'] is None  # names come from Master Data on save
    hierarchy = row['geo_code_hierarchy_json']
    assert hierarchy['lowest_level_value_id'] == 'ET040404888003'
    assert [(h['level_id'], h['level_mnemonic'], h['level_value_id']) for h in hierarchy['hierarchy']] == [
        ('l1', 'region', 'ET04'), ('l2', 'zone', 'ET0404'), ('l3', 'woreda', 'ET040404'),
        ('l4', 'kebele', 'ET040404888003')]


def test_v5_location_stops_at_the_deepest_submitted_level():
    row = render({'location_source': 'mds', 'region_code': 'ET04', 'zone_code': 'ET0404',
                  'woreda_code': 'ET040404'})['ls_livestock_location'][0]
    assert row['kebele_id'] is None
    assert row['geo_lowest_level_value_id'] == 'ET040404'
    assert row['geo_code_hierarchy_json']['hierarchy'][-1]['level_value_id'] == 'ET040404'


def test_older_forms_keep_names_without_ids_or_hierarchy():
    row = render({'region': 'oromia', 'zone': 'East Shewa', 'woreda': "Ada'a", 'kebele': 'Dire Arerti'})['ls_livestock_location'][0]
    assert row['woreda'] == "Ada'a"
    assert 'woreda_id' not in row and 'geo_code_hierarchy_json' not in row
