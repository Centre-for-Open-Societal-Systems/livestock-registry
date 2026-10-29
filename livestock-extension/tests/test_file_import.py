"""The native "Import from file" menu: the Livestock intake form has its own file-import data model whose key
paths, pattern and Jinja template take one flat CSV or Excel row; the ODK connector's model stays as it was.
The custom ImportBatch register it replaces is retired."""
import hashlib
import importlib
import json
import os
import re
from pathlib import Path

import pytest
from jinja2 import Environment
from jinja2.exceptions import UndefinedError

PACKAGE = os.environ.get('REGISTRY_EXTENSION_MODULE', 'openg2p_registry_livestock_extension')
ROOT = Path(importlib.import_module(PACKAGE).__file__).parent
REPO = ROOT.parents[2]
META = ROOT / 'meta_data'

pytestmark = pytest.mark.skipif('livestock' not in PACKAGE, reason='livestock import')

REGISTER = '997676d3-7008-59f9-b23e-613ad79bbb08'
FORM = 'e92e8be1-207f-518e-99c2-8bc21cc1f112'
CONFIG = '5353b3ca-1ee0-550c-a672-978cd478aead'
MODEL = 'file_import_to_livestock_intake'
TEMPLATE = 'livestock_file_import_intake.j2'
IDENTITY = {'farmer_id', 'fayda_id'}
PERSONNEL = {'surveyor_name', 'surveyor_mobile_number', 'supervisor_name', 'supervisor_mobile_number'}
GEO = {'region', 'zone', 'woreda', 'kebele', 'latitude', 'longitude'}
ANIMAL = {'ear_tag_id', 'secondary_identifier', 'species', 'breed', 'quantity', 'weight', 'date_of_birth', 'age',
          'gender', 'health_status', 'vaccination_status', 'registration_date'}
ANIMAL_REQUIRED = {'species', 'breed', 'gender', 'health_status', 'vaccination_status', 'registration_date'}
CHILD_SECTIONS = {'ls_health_event_details', 'ls_vaccination_details',
                  'ls_vital_event_details', 'ls_breeding_details', 'ls_vaccine_schedule_details',
                  'ls_retagging_details', 'ls_import_batch_details', 'ls_audit_log_details'}
IDENTITY_ROW = {'farmer_id': 'FR-000000000001', 'fayda_id': '0000 1234 5678 9012'}
ANIMAL_ROW = {'ear_tag_id': 'ET0000000013', 'species': 'CATTLE', 'breed': 'BREED_LOCAL', 'date_of_birth': '2020-01-01',
              'gender': 'FEMALE', 'health_status': 'HEALTHY', 'vaccination_status': 'UP_TO_DATE',
              'registration_date': '2026-10-29'}
BASE = {**IDENTITY_ROW, **ANIMAL_ROW}
RETIRED_REGISTER = '0fd11be9-83d7-5d2e-9dea-e0653add7059'
ODK_SQL_SHA256 = 'e37a083e4b3d95562870d0f761a896dfd8d5c606403a1717b9bd36b92a61b4a8'
ODK_TEMPLATE_SHA256 = '39ea5144221de41b71a8db67a47bbd7d4c5c61f379293c82bffbc8c247d687e4'


def sql(folder, name):
    return (META / folder / name).read_text(encoding='utf-8')


def render(row, template=TEMPLATE):
    text = (ROOT / 'templates' / template).read_text(encoding='utf-8')
    return json.loads(Environment().from_string(text).render(expanded=row))


def header():
    return (REPO / 'import-templates' / 'livestock_intake_import_template.csv').read_text(encoding='utf-8').strip().split(',')


def section_widget_ids(section_id):
    """The widget ids of a register section as the base seed defines them (one row per line)."""
    for line in sql('register-metadata', 'g2p_register_sections.sql').splitlines():
        if f"'{section_id}'" in line:
            return set(re.findall(r'"widget-id": "(\w+)"', line))
    raise AssertionError(section_id)


def sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def test_import_configuration_has_a_fixed_id_and_points_at_the_form_own_data_model():
    text = sql('registry-configurations', 'g2p_registry_import_file_configurations.sql')
    assert re.search(rf"'{CONFIG}',\s*'{REGISTER}',\s*'{FORM}',\s*'{MODEL}',\s*'{MODEL}',\s*'Import livestock intakes", text)
    assert 'ON CONFLICT (import_file_configuration_id) DO UPDATE' in text
    assert 'data_model_id = EXCLUDED.data_model_id' in text and 'import_file_template_mnemonic = EXCLUDED' in text
    assert 'odk_to_livestock_intake' not in re.sub(r'^--.*$', '', text, flags=re.MULTILINE)
    assert len(re.findall(r"^\(\s*$", text, re.MULTILINE)) == 1, 'one row per livestock intake form'
    assert f"('{FORM}','{REGISTER}'" in sql('register-metadata', 'g2p_intake_form_definitions.sql').replace('\n', '')


def test_data_model_key_paths_pattern_and_template_rows_are_upserts_on_the_import_envelope():
    seed = sql('zz-oan', '50_file_import_to_livestock_intake.sql')
    assert f"('{MODEL}','FILE_IMPORT_TO_LIVESTOCK_INTAKE','$.headers.sender_id=>^Staff Portal$',NULL,TRUE)" in seed
    assert (f"('{MODEL}_key_path','{MODEL}','$.headers.message_id','$.headers.sender_id',"
            f"'$.headers.signature','$.body','FALSE','')") in seed
    assert re.search(rf"\('{MODEL}_pattern','{MODEL}','{REGISTER}','{FORM}',[^\n]*,'\$\.body',"
                     rf"'G2PPassThroughEnricherService'\)", seed)
    assert (f"('{MODEL}_document','{TEMPLATE}','templates','{TEMPLATE}','seeder'") in seed
    assert f"('{MODEL}_template','{REGISTER}','{MODEL}','{MODEL}_document','FALSE'" in seed
    for key in ('"data_model_id"', '"key_path_id"', '"semantic_pattern_id"', '"document_id"', '"template_id"'):
        assert f'ON CONFLICT ({key}) DO UPDATE' in seed
    assert 'DO NOTHING' not in seed and 'NOT IN' not in seed
    assert (ROOT / 'templates' / TEMPLATE).is_file()


def test_pattern_enricher_is_the_pass_through_and_not_a_dci_or_odk_one():
    enrichers = importlib.import_module(PACKAGE + '.ingestion_pipeline.enricher_services')
    service = enrichers.G2PPassThroughEnricherService()
    payload = {'farmer_id': 'FR-000000000001'}
    assert service.enrich(payload, None) is payload
    seed = sql('zz-oan', '50_file_import_to_livestock_intake.sql')
    classes = re.findall(r"'(G2P\w+EnricherService)'", seed)
    assert classes == ['G2PPassThroughEnricherService']


def test_the_odk_connector_model_template_and_names_are_untouched_and_unique():
    odk = ROOT / 'meta_data' / 'zz-oan' / '20_odk_to_livestock_intake.sql'
    assert sha256(odk) == ODK_SQL_SHA256
    assert sha256(ROOT / 'templates' / 'odk_to_livestock_intake.j2') == ODK_TEMPLATE_SHA256
    text = odk.read_text(encoding='utf-8')
    assert re.search(r"'odk_to_livestock_intake_key_path','odk_to_livestock_intake','\$\.body\.header\.message_id',"
                     r"'\$\.body\.header\.sender_id',\s*'\$\.body\.header\.signature','\$\.body\[''header'',''message'']'", text)
    assert "'$.body.message.payload','G2PDciLivestockCreateEnricherService'" in text
    seed = sql('zz-oan', '50_file_import_to_livestock_intake.sql')
    assert not re.search(r"odk_to_livestock_intake'?[,)]", re.sub(r'^--.*$', '', seed, flags=re.MULTILINE))
    names = re.findall(r"'([\w.]+\.j2)','templates'", ''.join(
        sql(folder, name) for folder, name in (
            ('register-metadata', 'g2p_registry_documents.sql'), ('zz-oan', '20_odk_to_livestock_intake.sql'),
            ('zz-oan', '50_file_import_to_livestock_intake.sql'))))
    assert len(names) == len(set(names)) and TEMPLATE in names
    assert TEMPLATE.startswith('livestock_')


def test_blank_file_is_header_only_and_every_column_is_documented():
    path = REPO / 'import-templates' / 'livestock_intake_import_template.csv'
    raw = path.read_bytes()
    assert b'\r' not in raw
    lines = raw.decode('utf-8').splitlines()
    assert len(lines) == 1, 'sample rows belong in openg2p-data'
    columns = lines[0].split(',')
    assert len(columns) == len(set(columns)) and IDENTITY <= set(columns)
    doc = (REPO / 'docs/file-import.md').read_text(encoding='utf-8')
    section = doc.split('## Livestock intake')[1].split('\n## ')[0]
    documented = dict(re.findall(r'^\| `(\w+)` \|[^|]*\|\s*(Yes|No|Conditional) \|', section, re.MULTILINE))
    assert list(documented) == columns
    assert {c for c, required in documented.items() if required == 'Yes'} == IDENTITY | ANIMAL_REQUIRED
    assert {c for c, required in documented.items() if required == 'Conditional'} == {
        'ear_tag_id', 'secondary_identifier', 'quantity', 'date_of_birth'}


def animal_column_keys():
    for line in sql('register-metadata', 'g2p_register_sections.sql').splitlines():
        if "'livestock_animal_details_section_01'" in line:
            return set(re.findall(r'"column-key": "(\w+)"', line))
    raise AssertionError


def animal_section_schema():
    """The animal section as seeded, with the table required the way zzzzzzzzzz_required_animal_row.sql makes it."""
    for line in sql('register-metadata', 'g2p_register_sections.sql').splitlines():
        if "'livestock_animal_details_section_01'" in line:
            start = line.index("'{") + 1
            schema, _ = json.JSONDecoder().raw_decode(line[start:])
            break
    else:
        raise AssertionError

    def require(node):
        if isinstance(node, dict):
            if node.get('widget-id') == 'ls_animal_details_table':
                node['widget-required'] = True
            for value in node.values():
                require(value)
        elif isinstance(node, list):
            for value in node:
                require(value)

    require(schema)
    return schema


def test_columns_are_the_register_fields_of_the_flat_sections_and_the_one_animal_row():
    columns = set(header())
    assert columns == IDENTITY | PERSONNEL | GEO | ANIMAL
    assert PERSONNEL <= section_widget_ids('livestock_survey_personnel_section_02')
    assert IDENTITY <= set(re.findall(r'"widget-id": "(\w+)"', sql('zz-oan', '10_farmer_lookup.sql')))
    assert ANIMAL <= animal_column_keys()
    full = {**BASE, 'surveyor_name': 'Sample Surveyor', 'surveyor_mobile_number': '0911000000',
            'supervisor_name': 'Sample Supervisor', 'supervisor_mobile_number': '0922000000',
            'region': 'ET04', 'zone': 'ET0404', 'woreda': 'ET040404', 'kebele': 'ET040404888003',
            'latitude': '9.01', 'longitude': '38.74', 'secondary_identifier': 'BAND-1', 'quantity': '3',
            'weight': '250.5', 'age': '6 years'}
    assert set(full) == columns
    result = render(full)
    assert set(result) == {'livestock_farmer_lookup', 'ls_survey_personnel', 'ls_livestock_location', 'ls_animal_details'}
    assert not CHILD_SECTIONS & set(result)
    assert set(result['ls_survey_personnel'][0]) == PERSONNEL
    assert set(result['ls_livestock_location'][0]) == {
        'region_id', 'zone_id', 'woreda_id', 'kebele_id', 'geo_lowest_level_value_id', 'geo_code_hierarchy_json',
        'latitude', 'longitude'}
    assert set(result['ls_animal_details'][0]) == ANIMAL
    assert result['ls_animal_details'][0]['quantity'] == 3 and result['ls_animal_details'][0]['weight'] == 250.5


def test_one_row_produces_one_animal_row():
    result = render(BASE)
    assert result['ls_animal_details'] == [{
        'ear_tag_id': 'ET0000000013', 'species': 'CATTLE', 'breed': 'BREED_LOCAL', 'date_of_birth': '2020-01-01',
        'gender': 'FEMALE', 'health_status': 'HEALTHY', 'vaccination_status': 'UP_TO_DATE',
        'registration_date': '2026-10-29'}]
    assert result['livestock_farmer_lookup'][0]['total_animals'] == 1
    messy = render({**BASE, 'ear_tag_id': ' et 0000000013 ', 'species': ' cattle ', 'gender': 'female',
                    'registration_date': '2026-10-29 00:00:00'})['ls_animal_details']
    assert len(messy) == 1 and messy[0]['ear_tag_id'] == 'ET0000000013' and messy[0]['species'] == 'CATTLE'
    assert messy[0]['gender'] == 'FEMALE' and messy[0]['registration_date'] == '2026-10-29'


def test_the_rendered_intake_passes_the_finalize_rule_that_refuses_an_intake_without_an_animal():
    required_fields = importlib.import_module(PACKAGE + '.required_fields')
    schema = animal_section_schema()
    messages = required_fields.MESSAGES
    assert required_fields.section_problems(schema, True, [], {}, messages) == ['Livestock Details: add at least one row']
    records = render(BASE)['ls_animal_details']
    assert required_fields.section_problems(schema, True, records, {}, messages) == []
    for column in sorted(ANIMAL_REQUIRED):
        without = {k: v for k, v in records[0].items() if k != column}
        assert required_fields.section_problems(schema, True, [without], {}, messages), column


def test_farmer_lookup_is_a_typed_fan_with_the_animal_count():
    assert render(BASE)['livestock_farmer_lookup'] == [{
        'record_name': 'FR-000000000001', 'farmer_id': 'FR-000000000001', 'fayda_fin': None,
        'fayda_fan_id': '0000123456789012', 'status': 'ACTIVE', 'state': 'DRAFT', 'total_animals': 1}]


def test_typed_fin_and_header_case_and_spacing():
    result = render({**ANIMAL_ROW, 'Farmer_ID': ' fr-000000000001 ', 'FAYDA_ID': '123456789012', 'Surveyor_Name': ' Sample '})
    lookup = result['livestock_farmer_lookup'][0]
    assert (lookup['farmer_id'], lookup['fayda_fin'], lookup['fayda_fan_id']) == ('FR-000000000001', '123456789012', None)
    assert result['ls_survey_personnel'] == [{'surveyor_name': 'Sample'}]


def test_identity_location_and_personnel_match_what_the_odk_template_renders_for_the_same_holding():
    identity = {'farmer_id': 'FR-000000000001', 'fayda_id': '0000123456789012'}
    odk = render({'farmer': identity,
                  'location': {'location_source': 'mds', 'region_code': 'ET04', 'zone_code': 'ET0404',
                               'woreda_code': 'ET040404', 'kebele_code': 'ET040404888003'},
                  'survey_personnel': {'surveyor_name': 'Sample', 'surveyor_mobile_number': '1',
                                       'supervisor_name': 'Chief', 'supervisor_mobile_number': '2'},
                  'livestock': [{'species_id': 'cattle', 'breed': 'local', 'gender': 'female', 'ear_tag_id': 'ET0000000013',
                                 'date_of_birth': '2020-01-01', 'registration_date': '2026-10-29',
                                 'health_status': 'healthy', 'vaccination_status': 'up_to_date'}]}, 'odk_to_livestock_intake.j2')
    actual = render({**BASE, 'surveyor_name': 'Sample', 'surveyor_mobile_number': '1', 'supervisor_name': 'Chief',
                     'supervisor_mobile_number': '2', 'region': 'ET04', 'zone': 'ET0404', 'woreda': 'ET040404',
                     'kebele': 'ET040404888003'})
    for key in ('farmer_id', 'fayda_fin', 'fayda_fan_id', 'record_name', 'status', 'state', 'total_animals'):
        assert actual['livestock_farmer_lookup'][0][key] == odk['livestock_farmer_lookup'][0][key], key
    assert actual['ls_survey_personnel'] == odk['ls_survey_personnel']
    for key, value in actual['ls_livestock_location'][0].items():
        assert odk['ls_livestock_location'][0][key] == value, key


def test_location_stops_at_the_deepest_level_given_and_numbers_become_numbers():
    location = render({**BASE, 'region': 'et04', 'zone': 'ET0404', 'latitude': '-9.5', 'longitude': '38'})['ls_livestock_location'][0]
    assert location['geo_lowest_level_value_id'] == 'ET0404'
    assert [h['level_value_id'] for h in location['geo_code_hierarchy_json']['hierarchy']] == ['ET04', 'ET0404']
    assert 'woreda_id' not in location and location['latitude'] == -9.5 and location['longitude'] == 38.0


@pytest.mark.parametrize('change,message', [
    ({'farmer_id': 'FR-1'}, 'column farmer_id'),
    ({'farmer_id': ''}, 'column farmer_id'),
    ({'fayda_id': '12345'}, 'column fayda_id'),
    ({'fayda_id': ''}, 'column fayda_id'),
    ({'species': ''}, 'column species is required'),
    ({'breed': ''}, 'column breed is required'),
    ({'gender': ''}, 'column gender is required'),
    ({'gender': 'OTHER'}, 'column gender must be one of MALE, FEMALE, MIXED'),
    ({'health_status': 'well'}, 'column health_status must be one of'),
    ({'vaccination_status': ''}, 'column vaccination_status is required'),
    ({'registration_date': ''}, 'column registration_date is required'),
    ({'registration_date': '29/10/2026'}, 'column registration_date must be a date'),
    ({'date_of_birth': 'last year'}, 'column date_of_birth must be a date'),
    ({'weight': 'heavy'}, 'column weight must be a number'),
    ({'quantity': 'many'}, 'column quantity must be a number'),
    ({'latitude': 'north', 'longitude': '38'}, 'column latitude must be a number'),
    ({'latitude': '91', 'longitude': '38'}, 'column latitude must be between'),
    ({'latitude': '9', 'longitude': '181'}, 'column longitude must be between'),
    ({'latitude': '9'}, 'columns latitude and longitude must be given together'),
    ({'kebele': 'ET040404888003'}, 'column kebele needs the level above it'),
    ({'region': 'ET04', 'woreda': 'ET040404'}, 'column woreda needs the level above it'),
])
def test_a_value_the_register_cannot_take_fails_the_row_naming_the_column(change, message):
    with pytest.raises(UndefinedError, match=message):
        render({**BASE, **change})


def test_import_batch_register_is_not_seeded_and_the_retire_patch_deletes_by_explicit_id_children_first():
    for folder in ('register-metadata', 'registry-configurations', 'zz-oan'):
        for path in sorted((META / folder).glob('*.sql')):
            if path.name == '40_retire_import_batch_register.sql':
                continue
            text = path.read_text(encoding='utf-8')
            assert RETIRED_REGISTER not in text, path.name
            assert 'livestock_import_batch_details_section_01' not in text, path.name
            assert 'ls_import_batch_details' not in text, path.name
    patch = re.sub(r'^--.*$', '', sql('zz-oan', '40_retire_import_batch_register.sql'), flags=re.MULTILINE)
    assert 'NOT IN' not in patch.upper()
    deletes = re.findall(r'DELETE FROM "public"\."(\w+)"', patch)
    assert deletes == ['g2p_register_ui_tab_sections', 'g2p_register_sections', 'g2p_register_schemas',
                       'g2p_register_definitions']
    assert patch.count(RETIRED_REGISTER) >= 4
    assert 'DROP TABLE' not in patch.upper() and 'TRUNCATE' not in patch.upper()
    assert "'84721b63-f862-5ca7-aba5-fee321f2564b'" in patch
    tabs = sql('register-metadata', 'g2p_register_ui_tabs.sql')
    assert "'livestock_import_batch_tab'" in tabs and 'Imports & Audit' not in tabs


def test_import_batch_code_is_gone_from_the_extension():
    models = importlib.import_module(PACKAGE + '.register_domain.models')
    services = importlib.import_module(PACKAGE + '.register_domain.services')
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    for name in ('G2PRegisterImportBatch', 'G2PRegisterHistoryImportBatch', 'G2PIntakeFormImportBatch',
                 'ImportSourceSystemEnum', 'ImportStateEnum'):
        assert not hasattr(models, name), name
        assert name not in app
    assert not hasattr(services, 'G2PRegisterDomainServiceImportBatch')
    assert 'ImportBatch' not in app
    for relative in ('register_domain/models/import_batch.py', 'register_domain/schemas/import_batch.py',
                     'register_domain/services/g2p_register_domain_service_import_batch.py'):
        assert not (ROOT / relative).exists(), relative
    assert 'importbatch' not in (ROOT / 'register_domain/id_generator/g2p_id_generator_service.py').read_text(encoding='utf-8')
