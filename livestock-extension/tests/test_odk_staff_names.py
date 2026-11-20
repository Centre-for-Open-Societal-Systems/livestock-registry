"""A vet's or AI technician's ID is never sent as their name.

The livestock form asks for the ID (veterinarian_id, ai_technician_id); the
record's name fields accept letters only. A submission with an ID and no name
was refused at "Veterinarian Name (row 1)" / "AI Technician Name (row 1)"
because the template sent the ID (VET-001, AIT-07) as the name. The name is
now taken from the name fields only, and stays empty when none is given.
"""
import importlib
import json
import os
from pathlib import Path

import pytest
from jinja2 import Environment

PACKAGE = os.environ.get('REGISTRY_EXTENSION_MODULE', 'openg2p_registry_livestock_extension')
ROOT = Path(importlib.import_module(PACKAGE).__file__).parent

pytestmark = pytest.mark.skipif('livestock' not in PACKAGE, reason='livestock transform')


def render(animal):
    data = {'farmer': {'farmer_id': 'FR-000000000001', 'fayda_id': '001234567890'},
            'location': {'location_source': 'mds', 'region_code': 'ET01', 'zone_code': 'ET0101',
                         'woreda_code': 'ET010101', 'kebele_code': 'ET01010101'},
            'livestock': [{'species_id': 'cattle', 'breed': 'local', 'gender': 'female',
                           'primary_identifier': 'ANIMAL-001', 'date_of_birth': '2020-01-01', **animal}]}
    template = (ROOT / 'templates' / 'odk_to_livestock_intake.j2').read_text(encoding='utf-8')
    return json.loads(Environment().from_string(template).render(expanded=data))


def values(output, key):
    found = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == key:
                    found.append(v)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(output)
    return found


ANIMAL = {
    'health_events': [{'event_type': 'treatment', 'date_onset': '2026-09-10', 'veterinarian_id': 'VET-001'}],
    'breeding_events': [{'breeding_event_type': 'artificial_insemination', 'breeding_date': '2025-12-20',
                         'artificial_insemination_tab': {'ai_technician_id': 'AIT-07'}}],
}


def test_an_id_without_a_name_is_not_sent_as_the_name():
    output = render(ANIMAL)
    vets, technicians = values(output, 'veterinarian_name'), values(output, 'ai_technician_name')
    assert vets and technicians
    assert 'VET-001' not in vets
    assert 'AIT-07' not in technicians


def test_a_given_name_is_kept():
    animal = {
        'health_events': [dict(ANIMAL['health_events'][0], veterinarian_name='Abebe Kebede')],
        'breeding_events': [dict(ANIMAL['breeding_events'][0], artificial_insemination_tab={
            'ai_technician_id': 'AIT-07', 'ai_technician_name': 'Tigist Haile'})],
    }
    output = render(animal)
    assert 'Abebe Kebede' in values(output, 'veterinarian_name')
    assert 'Tigist Haile' in values(output, 'ai_technician_name')


def test_the_template_never_reads_an_id_into_a_name():
    template = (ROOT / 'templates' / 'odk_to_livestock_intake.j2').read_text(encoding='utf-8')
    for line in template.splitlines():
        if '"veterinarian_name"' in line or '"ai_technician_name"' in line:
            assert '_id' not in line.split(':', 1)[1], line


def technician(tab):
    output = render({'breeding_events': [{'breeding_event_type': 'artificial_insemination',
                                          'breeding_date': '2025-12-20', 'artificial_insemination_tab': tab}]})
    return values(output, 'ai_technician_name')[0]


# Form v8 and earlier have only the "AI technician" answer (ai_technician_id); officers wrote a
# name or an ID there. Until every phone has v9, a letters-only answer is the name.

def test_a_v8_answer_that_is_a_name_is_used_as_the_name():
    assert technician({'ai_technician_id': 'Tigist Haile'}) == 'Tigist Haile'
    assert technician({'ai_technician_id': " O'Brien-Tesfaye "}) == "O'Brien-Tesfaye"
    assert technician({'ai_technician_id': 'ትግስት ኃይሌ'}) == 'ትግስት ኃይሌ'


def test_a_v8_answer_that_looks_like_an_id_is_refused():
    for answer in ('AIT-07', 'VET 001', '12345', 'T.Haile', 'a' * 101, '', '  '):
        assert technician({'ai_technician_id': answer}) is None, answer


def test_the_v9_name_question_wins_over_the_v8_answer():
    assert technician({'ai_technician_id': 'Abebe Kebede', 'ai_technician_name': 'Tigist Haile'}) == 'Tigist Haile'
    assert technician({'ai_technician_id': 'AIT-07', 'ai_technician_name': 'Tigist Haile'}) == 'Tigist Haile'
