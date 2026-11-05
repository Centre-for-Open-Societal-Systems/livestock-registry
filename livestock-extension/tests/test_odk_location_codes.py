"""Form v5 submissions carry Master Data geo unit ids (P-codes) and the record
gets the hierarchy document the staff portal's geo-hierarchy widget reads."""
import csv
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
                  'woreda_code': 'ET040404', 'kebele_code': 'ET04040404'})['ls_livestock_location'][0]
    assert (row['region_id'], row['zone_id'], row['woreda_id'], row['kebele_id']) == (
        'ET04', 'ET0404', 'ET040404', 'ET04040404')
    assert row['geo_lowest_level_value_id'] == 'ET04040404'
    assert row['region'] is None and row['kebele'] is None  # names come from Master Data on save
    hierarchy = row['geo_code_hierarchy_json']
    assert hierarchy['lowest_level_value_id'] == 'ET04040404'
    assert [(h['level_id'], h['level_mnemonic'], h['level_value_id']) for h in hierarchy['hierarchy']] == [
        ('l1', 'region', 'ET04'), ('l2', 'zone', 'ET0404'), ('l3', 'woreda', 'ET040404'),
        ('l4', 'kebele', 'ET04040404')]


def test_v5_location_stops_at_the_deepest_submitted_level():
    row = render({'location_source': 'mds', 'region_code': 'ET04', 'zone_code': 'ET0404',
                  'woreda_code': 'ET040404'})['ls_livestock_location'][0]
    assert row['kebele_id'] is None
    assert row['geo_lowest_level_value_id'] == 'ET040404'
    assert row['geo_code_hierarchy_json']['hierarchy'][-1]['level_value_id'] == 'ET040404'


def test_older_forms_keep_names_without_ids_or_hierarchy():
    row = render({'region': 'oromia', 'zone': 'East Shewa', 'woreda': "Ada'a", 'kebele': 'Qanani'})['ls_livestock_location'][0]
    assert row['woreda'] == "Ada'a"
    assert 'woreda_id' not in row and 'geo_code_hierarchy_json' not in row


ODK = Path(__file__).resolve().parents[2] / 'odk'
LEVELS = ('region', 'zone', 'woreda', 'kebele')


def media(level):
    with (ODK / 'media' / f'{level}_odk.csv').open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def test_v7_form_submission_builds_the_hierarchy():
    """The v7 form's location group, as Central returns it, with the hidden
    location_source question and the four *_code answers."""
    submissions = json.loads((ODK / 'sample_submissions.json').read_text(encoding='utf-8'))['value']
    codes = {level: {row['name'] for row in media(level)} for level in LEVELS}
    for submission in submissions:
        location = submission['location']
        assert set(location) == {'region_code', 'zone_code', 'woreda_code', 'kebele_code', 'location_source'}
        chain = [location[f'{level}_code'] for level in LEVELS]
        for level, code in zip(LEVELS, chain):
            assert code in codes[level], f'{code} is not in {level}_odk.csv'
        assert all(child.startswith(parent) for parent, child in zip(chain, chain[1:]))
        row = render(location)['ls_livestock_location'][0]
        assert [h['level_value_id'] for h in row['geo_code_hierarchy_json']['hierarchy']] == chain
        assert row['geo_lowest_level_value_id'] == chain[-1]


def test_every_place_hangs_under_a_listed_parent_with_a_prefixed_code():
    codes = {level: {row['name'] for row in media(level)} for level in LEVELS}
    for level, parent_level in zip(LEVELS[1:], LEVELS):
        for row in media(level):
            assert row[parent_level] in codes[parent_level], row
            assert row['name'].startswith(row[parent_level]), row


def test_codes_are_unique_and_no_label_repeats_under_one_parent():
    for level, parent_level in zip(LEVELS, (None,) + LEVELS):
        rows = media(level)
        assert len({row['name'] for row in rows}) == len(rows), level
        labels = [(row[parent_level] if parent_level else '', row['label']) for row in rows]
        assert len(set(labels)) == len(labels), level
        assert all(row['label'] == row['label'].strip() and '_' not in row['label'] and '  ' not in row['label'] for row in rows)
