-- Record header with the record status, as the OpenG2P reference and farmer
-- registries have it (header-section widget with status and statusReason). It
-- shows the record's status (Active, Inactive, Archived) and the reason, and it
-- is the section a change request uses to close a record: an approved UPDATE
-- of record_status and record_status_reason on this section. Search and export
-- show only ACTIVE records (platform default), so a closed record leaves the
-- lists but keeps its history. The platform accepts those two fields in a
-- change request only from a section that binds them, which no other section
-- does.
--
-- Sorts after the base section and tab-section files; no later file touches
-- these sections. Idempotent: the section upsert and the tab-section insert
-- re-run safely on every install and upgrade.
-- Livestock register, first section of the Livestock tab.
INSERT INTO "public"."g2p_register_sections" ("register_id","section_id","section_register_id","is_core_section","section_mnemonic","section_description","documents_required","no_of_verifications_required","is_list","section_weightage","section_ui_schema","cr_auto_approve_for_bene_portal","cr_auto_approve_for_agent_portal","cr_auto_approve_for_staff_portal","cr_auto_approve_for_partner") VALUES
('997676d3-7008-59f9-b23e-613ad79bbb08','livestock_record_header','997676d3-7008-59f9-b23e-613ad79bbb08','FALSE','ls_record_header','Record status','FALSE',0,'FALSE',0,'{"panels": [{"panels": [{"widgets": [{"widget": "header-section", "widget-id": "registry-header", "widget-type": "group", "widget-data-path": {"name": "997676d3-7008-59f9-b23e-613ad79bbb08.record_name", "status": "997676d3-7008-59f9-b23e-613ad79bbb08.record_status", "createdAt": "997676d3-7008-59f9-b23e-613ad79bbb08.created_at", "createdBy": "997676d3-7008-59f9-b23e-613ad79bbb08.created_by", "functionalId": "997676d3-7008-59f9-b23e-613ad79bbb08.functional_record_id", "statusReason": "997676d3-7008-59f9-b23e-613ad79bbb08.record_status_reason", "lastApprovedAt": "997676d3-7008-59f9-b23e-613ad79bbb08.last_approved_at", "lastApprovedBy": "997676d3-7008-59f9-b23e-613ad79bbb08.last_approved_by"}, "widget-data-format": {"nameColor": "#ED7C22", "statusColors": {"ACTIVE": "#16A34A", "ARCHIVED": "#6B7280", "INACTIVE": "#D97706"}}, "widget-field-config": {"status": {"data-source": {"type": "static", "options": [{"label": "Active", "value": "ACTIVE"}, {"label": "Inactive", "value": "INACTIVE"}, {"label": "Archived", "value": "ARCHIVED"}]}}}}], "panel-id": "livestock_record_header_inside_panel", "panel-orientation": "vertical"}], "panel-id": "livestock_record_header_outside_panel", "panel-orientation": "horizontal"}], "section-id": "livestock_record_header", "section-title": "", "section-editable": true}','FALSE','FALSE','FALSE','FALSE')
ON CONFLICT ("section_id") DO UPDATE SET
  "section_ui_schema"   = EXCLUDED."section_ui_schema",
  "section_description" = EXCLUDED."section_description";

INSERT INTO "public"."g2p_register_ui_tab_sections" ("tab_section_id","register_id","tab_id","section_id","section_order") VALUES
('bb65522f-0459-56a1-9852-0546b3922cdc','997676d3-7008-59f9-b23e-613ad79bbb08','livestock_livestock_tab','livestock_record_header',5)
ON CONFLICT DO NOTHING;

-- Livestock's Farmer register, first section of the Farmer tab.
INSERT INTO "public"."g2p_register_sections" ("register_id","section_id","section_register_id","is_core_section","section_mnemonic","section_description","documents_required","no_of_verifications_required","is_list","section_weightage","section_ui_schema","cr_auto_approve_for_bene_portal","cr_auto_approve_for_agent_portal","cr_auto_approve_for_staff_portal","cr_auto_approve_for_partner") VALUES
('f9c6a359-9563-5a43-b0fe-6c7e452037a3','livestock_farmer_record_header','f9c6a359-9563-5a43-b0fe-6c7e452037a3','FALSE','ls_farmer_record_header','Record status','FALSE',0,'FALSE',0,'{"panels": [{"panels": [{"widgets": [{"widget": "header-section", "widget-id": "registry-header", "widget-type": "group", "widget-data-path": {"name": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.record_name", "status": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.record_status", "createdAt": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.created_at", "createdBy": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.created_by", "functionalId": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.functional_record_id", "statusReason": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.record_status_reason", "lastApprovedAt": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.last_approved_at", "lastApprovedBy": "f9c6a359-9563-5a43-b0fe-6c7e452037a3.last_approved_by"}, "widget-data-format": {"nameColor": "#ED7C22", "statusColors": {"ACTIVE": "#16A34A", "ARCHIVED": "#6B7280", "INACTIVE": "#D97706"}}, "widget-field-config": {"status": {"data-source": {"type": "static", "options": [{"label": "Active", "value": "ACTIVE"}, {"label": "Inactive", "value": "INACTIVE"}, {"label": "Archived", "value": "ARCHIVED"}]}}}}], "panel-id": "livestock_farmer_record_header_inside_panel", "panel-orientation": "vertical"}], "panel-id": "livestock_farmer_record_header_outside_panel", "panel-orientation": "horizontal"}], "section-id": "livestock_farmer_record_header", "section-title": "", "section-editable": true}','FALSE','FALSE','FALSE','FALSE')
ON CONFLICT ("section_id") DO UPDATE SET
  "section_ui_schema"   = EXCLUDED."section_ui_schema",
  "section_description" = EXCLUDED."section_description";

INSERT INTO "public"."g2p_register_ui_tab_sections" ("tab_section_id","register_id","tab_id","section_id","section_order") VALUES
('cabe2922-d5fb-526c-b2f3-f34d1d44057d','f9c6a359-9563-5a43-b0fe-6c7e452037a3','livestock_farmer_tab','livestock_farmer_record_header',5)
ON CONFLICT DO NOTHING;
