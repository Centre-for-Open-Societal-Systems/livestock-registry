"""Schema moves preserve every owning form, rather than waiving missing fields."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest
SPEC = importlib.util.spec_from_file_location('metadata_comparison',Path(__file__).resolve().parents[1]/'ci/refactor/compare_new_dev.py')
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


def fixture():
    path = 'register.crop_year'
    rows = [{'section_id':'identity','section_register_id':'register','removed_field_paths':[path]}]
    metadata = {'g2p_register_sections':[{'section_id':'season','section_register_id':'register',
        'section_ui_schema':{'section-required-for-submit':True,'widgets':[{'widget':'number','widget-data-path':path}]}}],
        'g2p_intake_form_ui_tab_sections':[{'tab_id':tab,'section_id':section} for tab in ('planning','cultivation','sowing','production') for section in ('identity','season')],
        'g2p_register_ui_tab_sections':[]}
    rule = {'from_section':'identity','to_section':'season','path':path,'mechanism':'section_move'}
    return rows,metadata,[rule]


@pytest.mark.parametrize('failure',[None,'one-tab-missing','field-missing','register-changed','not-required','unreviewed','duplicate-rule'])
def test_move_requires_same_field_register_and_every_intake_tab(failure):
    rows,metadata,rules = fixture()
    if failure=='one-tab-missing': metadata['g2p_intake_form_ui_tab_sections'].remove({'tab_id':'production','section_id':'season'})
    if failure=='field-missing': metadata['g2p_register_sections'][0]['section_ui_schema']['widgets']=[]
    if failure=='register-changed': metadata['g2p_register_sections'][0]['section_register_id']='another-register'
    if failure=='not-required': metadata['g2p_register_sections'][0]['section_ui_schema']['section-required-for-submit']=False
    if failure=='unreviewed': rules=[]
    if failure=='duplicate-rule': rules.append(deepcopy(rules[0]))
    comparison.reconcile_sections(rows,metadata,rules)
    assert bool(rows[0]['unexplained_removed_field_paths']) == bool(failure)


@pytest.mark.parametrize('failure',[None,'editable','not-display','no-register-binding','original-still-register-section'])
def test_source_projection_must_remain_registered_read_only_display(failure):
    rows,metadata,rules = fixture()
    rules[0]['mechanism']='approved_farmer_projection'
    widget=metadata['g2p_register_sections'][0]['section_ui_schema']['widgets'][0]
    widget.update(widget='display',**{'widget-readonly':True})
    metadata['g2p_register_ui_tab_sections']=[{'tab_id':'register-tab','section_id':'season'}]
    if failure=='editable': widget['widget-readonly']=False
    if failure=='not-display': widget['widget']='text'
    if failure=='no-register-binding': metadata['g2p_register_ui_tab_sections']=[]
    if failure=='original-still-register-section': metadata['g2p_register_ui_tab_sections'].append({'tab_id':'register-tab','section_id':'identity'})
    comparison.reconcile_sections(rows,metadata,rules)
    assert bool(rows[0]['unexplained_removed_field_paths']) == bool(failure)
