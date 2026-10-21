-- Livestock code lists for the Master Data service (g2p_attributes).
-- Loaded by docker/db-seed/livestock-entrypoint.sh (load_code_lists) into the
-- Master Data database the registry reads over the Master Data API; the
-- registry itself keeps no copy since registry-platform 1.2. Idempotent: the
-- same ids upsert, nothing is deleted.
INSERT INTO "public"."g2p_attributes" ("attribute_id","attribute_code","attribute_display","is_hierarchical") VALUES 
('LIVESTOCK_SPECIES','LIVESTOCK_SPECIES','Species','FALSE'),
('LIVESTOCK_BREED','LIVESTOCK_BREED','Breed','TRUE'),
('VACCINE_TYPE','VACCINE_TYPE','Vaccine','TRUE'),
('LIVESTOCK_DISEASE','LIVESTOCK_DISEASE','Livestock Disease','FALSE'),
('APPROVAL_STATUS','APPROVAL_STATUS','Approval / Workflow Status','FALSE')
ON CONFLICT ("attribute_id") DO UPDATE SET
  "attribute_code" = EXCLUDED."attribute_code",
  "attribute_display" = EXCLUDED."attribute_display",
  "is_hierarchical" = EXCLUDED."is_hierarchical";
