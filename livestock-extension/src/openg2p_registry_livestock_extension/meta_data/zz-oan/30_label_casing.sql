-- Label casing: sentence case for everything staff read that OAN metadata defines.
-- Labels, section and tab titles, table headings, messages and dropdown filter
-- labels use sentence case; acronyms and proper nouns (ID, FAN, FIN, Fayda,
-- Kebele, Woreda, ODK, DA) keep their case, and raw codes are not shown as
-- labels. Only display text changes: translation keys, ids, codes and
-- mnemonics are untouched.
--
-- Every statement is an explicit-id UPDATE (or a merge of named translation
-- keys), so it is idempotent and a plain upgrade applies it to databases that
-- already hold the older text. It sorts after the older seed files of this
-- package, so it also wins on a fresh install.

-- Display labels: domain translations (English)
UPDATE "public"."registry_languages"
SET "domain_translation" = (COALESCE("domain_translation"::jsonb, '{}'::jsonb) ||
'{
 "access_to_finance": "Access to finance",
 "access_to_machinery": "Access to machinery",
 "add_crop": "Add crop",
 "add_farm": "Add farm",
 "add_farm_input": "Add farm input",
 "add_livestock_record": "Add livestock record",
 "add_member": "Add member",
 "address_line_1": "Address line 1",
 "address_line_2": "Address line 2",
 "A_LOT_OF_DIFFICULTY": "A lot of difficulty",
 "BIOFUELS_NONFOOD": "Biofuels (non-food)",
 "birth_date": "Birth date",
 "CANNOT_DO_AT_ALL": "Cannot do at all",
 "CAN_READ_AND_WRITE": "Can read and write",
 "certificate_storage_id": "Certificate storage ID",
 "click_to_search_household": "Click to search household",
 "computation_scores": "Computation scores",
 "cooperative_union": "Cooperative union",
 "cooperative_union_name": "Cooperative union name",
 "coss_input_ai_technician_name": "AI technician name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_applied_on_min": "Applied on: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_breeding_date_min": "Breeding date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_da_name": "DA name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_date_of_birth_min": "Date of birth: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_date_onset_min": "Date onset: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_date_resolution_min": "Date resolution: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_event_date_min": "Event date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_expected_calving_date_min": "Expected calving date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_farmer_name": "Farmer name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_first_name_amh": "First name Amharic: use 1-100 Ethiopic letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_first_name": "First name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_first_name_other": "First name other: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_last_name_amh": "Last name Amharic: use 1-100 Ethiopic letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_last_name": "Last name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_last_name_other": "Last name other: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_middle_name_amh": "Middle name Amharic: use 1-100 Ethiopic letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_middle_name": "Middle name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_middle_name_other": "Middle name other: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_next_due_date_min": "Next due date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_pregnancy_confirmation_date_min": "Pregnancy confirmation date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_registration_date_min": "Registration date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_retag_date_min": "Retag date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_state_date_min": "State date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_supervisor_name": "Supervisor name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_surveyor_name": "DA name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "coss_input_vaccination_date_min": "Vaccination date: the date is before 1900. Enter a date on or after 1900-01-01.",
 "coss_input_veterinarian_name": "Veterinarian name: use 1-100 letters, spaces, hyphens or apostrophes. Remove digits and other symbols.",
 "country_code": "Country code",
 "CROP_PRODUCTION": "Crop production",
 "CROP_SHARE": "Crop share",
 "current_land_use": "Current land use",
 "disability_severity": "Disability severity",
 "disability_type": "Disability type",
 "education_level": "Education level",
 "end_use": "End use",
 "enter_address_line_1": "Enter address line 1",
 "enter_address_line_2": "Enter address line 2",
 "enter_altitude": "Enter altitude",
 "enter_latitude": "Enter latitude",
 "enter_longitude": "Enter longitude",
 "estimated_age": "Estimated age",
 "farmer_cluster": "Farmer cluster",
 "farmer_cluster_role": "Farmer cluster role",
 "farmer_farm_inputs": "Farm inputs",
 "farmer_farm_inputs_tab": "Farm inputs",
 "farmer_household_information": "Household information",
 "farmer_household_location": "Household location",
 "farmer_household_members": "Household members",
 "farmer_ingestion_intake": "Farmer ingestion intake",
 "farmer_intake": "Farmer intake",
 "farmer_intake_tab": "Farmer intake",
 "farmer_personal_information": "Personal information",
 "farmer_socio_economic_and_health": "Socio-economic & health details",
 "farming_type": "Farming type",
 "farm_inputs": "Farm inputs",
 "FarmInputs": "Farm inputs",
 "FEED_ANIMALS": "Feed animals",
 "fertilizer_use": "Fertilizer use",
 "first_name": "First name",
 "FOOD_HUMAN_CONSUMPTION": "Food (human consumption)",
 "GOVERNMENT_NGO_SUPPORT": "Government / NGO support",
 "head_count": "Head count",
 "health_details": "Health details",
 "HIGHER_EDUCATION": "Higher education",
 "household_computation_scores": "Computation scores",
 "household_farmer_location_details": "Location details",
 "household_farmer_personal_information": "Personal information",
 "household_head": "Household head",
 "household_household_information": "Household information",
 "household_information": "Household information",
 "household_ingestion_intake": "Household ingestion intake",
 "household_intake_tab": "Household intake",
 "HouseholdMember": "Household members",
 "household_members": "Household members",
 "household_members_records": "Household members records",
 "household_socio_economic_and_health": "Socio-economic & health details",
 "improved_seed_use": "Improved seed use",
 "insecticide_use": "Insecticide use",
 "is_cooperative_union_member": "Is cooperative union member",
 "is_farmer_cluster_member": "Is farmer cluster member",
 "is_primary_cooperative_member": "Is primary cooperative member",
 "land_ownership_type": "Land ownership type",
 "land_size": "Land size",
 "last_name": "Last name",
 "LIVESTOCK_PRODUCTION": "Livestock production",
 "livestock_system": "Livestock system",
 "location_details": "Location details",
 "marital_status": "Marital status",
 "means_of_acquisition": "Means of acquisition",
 "MembershipDetails": "Membership details",
 "middle_name": "Middle name",
 "NO_DIFFICULTY": "No difficulty",
 "NOMADIC_PASTORAL": "Nomadic pastoral",
 "number_of_children": "Number of children",
 "number_of_female_members": "Number of female members",
 "number_of_male_members": "Number of male members",
 "num_female_members": "Number of female members",
 "num_male_members": "Number of male members",
 "other_land_owner": "Other land owner",
 "personal_information": "Personal information",
 "pesticide_use": "Pesticide use",
 "planted_date": "Planted date",
 "postal_code": "Postal code",
 "primary_cooperative_name": "Primary cooperative name",
 "primary_cooperative": "Primary cooperative",
 "search_by_name_or_id": "Search by name or ID",
 "SEDENTARY_PASTORAL": "Sedentary pastoral",
 "select_household": "Select household",
 "SELF_CARE": "Self care",
 "SEMI_NOMADIC": "Semi nomadic",
 "size_of_group": "Size of group",
 "socio_economic_and_health": "Socio-economic & health details",
 "socio_economic_details": "Socio economic details",
 "soil_fertility": "Soil fertility",
 "SOME_DIFFICULTY": "Some difficulty",
 "source_of_income": "Source of income",
 "SQUARE_FOOT": "Square foot",
 "SQUARE_KM": "Square km",
 "SQUARE_METER": "Square meter",
 "SQUARE_YARD": "Square yard",
 "sub_region": "Sub region",
 "water_source": "Water source",
 "year_of_acquisition": "Year of acquisition"
}'::jsonb)::json
WHERE "language_code" = 'en';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(section_ui_schema::text, '"section-title": "Farmer Details"', '"section-title": "Farmer details"')::jsonb, "section_description" = 'Livestock record'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_livestock_record_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "Vital Event Details"', '"widget-label": "Vital event details"'), '"widget-label": "Ear Tag / Secondary Identifier"', '"widget-label": "Ear tag / secondary identifier"'), '"widget-label": "Event Type"', '"widget-label": "Event type"'), '"label": "BIRTH"', '"label": "Birth"'), '"label": "MORTALITY"', '"label": "Mortality"'), '"label": "DISEASE"', '"label": "Disease"'), '"widget-label": "Event Date"', '"widget-label": "Event date"'), '"label": "ACCIDENT"', '"label": "Accident"'), '"label": "PREDATION"', '"label": "Predation"'), '"label": "SLAUGHTER"', '"label": "Slaughter"'), '"label": "HOME"', '"label": "Home"'), '"label": "VETERINARY"', '"label": "Veterinary"'), '"label": "MARKET"', '"label": "Market"'), '"label": "FIELD"', '"label": "Field"'), '"label": "QUARANTINE_CENTER"', '"label": "Quarantine center"'), '"widget-label": "Location Details"', '"widget-label": "Location details"'), '"widget-label": "Disease / Diagnosis"', '"widget-label": "Disease / diagnosis"'), '"widget-label": "Date of Onset"', '"widget-label": "Date of onset"'), '"widget-label": "Date of Resolution"', '"widget-label": "Date of resolution"'), '"notBeforeFieldMessage": "Date of Resolution cannot be before Date of Onset"', '"notBeforeFieldMessage": "Date of resolution cannot be before date of onset"'), '"widget-label": "Treatment Administered"', '"widget-label": "Treatment administered"'), '"widget-label": "Attending Veterinarian"', '"widget-label": "Attending veterinarian"'), '"widget-label": "Notifiable Disease"', '"widget-label": "Notifiable disease"'), '"widget-label": "Number of Offspring"', '"widget-label": "Number of offspring"'), '"widget-label": "Sex of Offspring"', '"widget-label": "Sex of offspring"'), '"label": "Mixed / Not Applicable"', '"label": "Mixed / not applicable"'), '"widget-label": "Reporting Officer"', '"widget-label": "Reporting officer"'), '"widget-data-dialog-title-add": "Add Vital Event Details"', '"widget-data-dialog-title-add": "Add vital event details"'), '"widget-data-dialog-title-edit": "Edit Vital Event Details"', '"widget-data-dialog-title-edit": "Edit vital event details"'), '"section-title": "Vital Event Details"', '"section-title": "Vital event details"')::jsonb, "section_description" = 'Vital event details'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_vital_event_details_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "DA Name"', '"widget-label": "DA name"'), '"widget-label": "DA Mobile Number"', '"widget-label": "DA mobile number"'), '"widget-label": "Supervisor Name"', '"widget-label": "Supervisor name"'), '"widget-label": "Supervisor Mobile Number"', '"widget-label": "Supervisor mobile number"'), '"section-title": "Survey Personnel"', '"section-title": "Survey personnel"')::jsonb, "section_description" = 'Survey personnel'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_survey_personnel_section_02';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "Vaccine Schedule Details"', '"widget-label": "Vaccine schedule details"'), '"widget-data-dialog-title-add": "Add Vaccine Schedule Details"', '"widget-data-dialog-title-add": "Add vaccine schedule details"'), '"widget-data-dialog-title-edit": "Edit Vaccine Schedule Details"', '"widget-data-dialog-title-edit": "Edit vaccine schedule details"'), '"section-title": "Vaccine Schedule Details"', '"section-title": "Vaccine schedule details"')::jsonb, "section_description" = 'Vaccine schedule details'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_vaccine_schedule_details_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "Breeding Details"', '"widget-label": "Breeding details"'), '"widget-label": "Ear Tag / Secondary Identifier"', '"widget-label": "Ear tag / secondary identifier"'), '"widget-label": "Breeding Type"', '"widget-label": "Breeding type"'), '"label": "NATURAL"', '"label": "Natural"'), '"label": "Artificial Insemination"', '"label": "Artificial insemination"'), '"widget-label": "Breeding Date"', '"widget-label": "Breeding date"'), '"widget-label": "Sire / Semen Source"', '"widget-label": "Sire / semen source"'), '"label": "HOME"', '"label": "Home"'), '"label": "VETERINARY"', '"label": "Veterinary"'), '"label": "MARKET"', '"label": "Market"'), '"label": "FIELD"', '"label": "Field"'), '"label": "QUARANTINE_CENTER"', '"label": "Quarantine center"'), '"widget-label": "Location Details"', '"widget-label": "Location details"'), '"widget-label": "AI Technician"', '"widget-label": "AI technician"'), '"widget-label": "Technique Used"', '"widget-label": "Technique used"'), '"widget-label": "Semen Batch Number"', '"widget-label": "Semen batch number"'), '"widget-label": "Expected Calving Date"', '"widget-label": "Expected calving date"'), '"widget-label": "Pregnancy Confirmed"', '"widget-label": "Pregnancy confirmed"'), '"widget-label": "Pregnancy Confirmation Date"', '"widget-label": "Pregnancy confirmation date"'), '"label": "PENDING"', '"label": "Pending"'), '"label": "SUCCESSFUL"', '"label": "Successful"'), '"label": "FAILED"', '"label": "Failed"'), '"widget-data-dialog-title-add": "Add Breeding Details"', '"widget-data-dialog-title-add": "Add breeding details"'), '"widget-data-dialog-title-edit": "Edit Breeding Details"', '"widget-data-dialog-title-edit": "Edit breeding details"'), '"section-title": "Breeding Details"', '"section-title": "Breeding details"')::jsonb, "section_description" = 'Breeding details'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_breeding_details_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "Health Event Details"', '"widget-label": "Health event details"'), '"widget-label": "Ear Tag / Secondary Identifier"', '"widget-label": "Ear tag / secondary identifier"'), '"widget-label": "Event Type"', '"widget-label": "Event type"'), '"label": "DISEASE"', '"label": "Disease"'), '"label": "INJURY"', '"label": "Injury"'), '"label": "TREATMENT"', '"label": "Treatment"'), '"label": "RECOVERY"', '"label": "Recovery"'), '"widget-label": "Date of Onset"', '"widget-label": "Date of onset"'), '"widget-label": "Date of Resolution"', '"widget-label": "Date of resolution"'), '"notBeforeFieldMessage": "Date of Resolution cannot be before Date of Onset"', '"notBeforeFieldMessage": "Date of resolution cannot be before date of onset"'), '"widget-label": "Notifiable Disease"', '"widget-label": "Notifiable disease"'), '"widget-label": "Treatment Administered"', '"widget-label": "Treatment administered"'), '"widget-label": "Veterinarian / Officer"', '"widget-label": "Veterinarian / officer"'), '"label": "HOME"', '"label": "Home"'), '"label": "VETERINARY"', '"label": "Veterinary"'), '"label": "MARKET"', '"label": "Market"'), '"label": "FIELD"', '"label": "Field"'), '"label": "QUARANTINE_CENTER"', '"label": "Quarantine center"'), '"widget-label": "Location Details"', '"widget-label": "Location details"'), '"widget-data-dialog-title-add": "Add Health Event Details"', '"widget-data-dialog-title-add": "Add health event details"'), '"widget-data-dialog-title-edit": "Edit Health Event Details"', '"widget-data-dialog-title-edit": "Edit health event details"'), '"section-title": "Health Event Details"', '"section-title": "Health event details"')::jsonb, "section_description" = 'Health event details'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_health_event_details_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "First Name"', '"widget-label": "First name"'), '"widget-label": "Middle Name"', '"widget-label": "Middle name"'), '"widget-label": "Last Name"', '"widget-label": "Last name"'), '"widget-label": "Date of Birth"', '"widget-label": "Date of birth"'), '"widget-label": "Mobile Number"', '"widget-label": "Mobile number"'), '"widget-label": "Registration Date"', '"widget-label": "Registration date"')::jsonb, "section_description" = 'Farmer identity'
WHERE "register_id" = 'f9c6a359-9563-5a43-b0fe-6c7e452037a3' AND "section_id" = 'livestock_farmer_identity_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "Ear Tag Replacement"', '"widget-label": "Ear tag replacement"'), '"widget-label": "Old Ear Tag"', '"widget-label": "Old ear tag"'), '"widget-label": "New Ear Tag"', '"widget-label": "New ear tag"'), '"widget-label": "Reason for Replacement"', '"widget-label": "Reason for replacement"'), '"widget-label": "Date of Retagging"', '"widget-label": "Date of retagging"'), '"widget-label": "Approving Officer"', '"widget-label": "Approving officer"'), '"widget-label": "Justification Notes"', '"widget-label": "Justification notes"'), '"widget-label": "Applied On"', '"widget-label": "Applied on"'), '"widget-data-dialog-title-add": "Add Ear Tag Replacement"', '"widget-data-dialog-title-add": "Add ear tag replacement"'), '"widget-data-dialog-title-edit": "Ear Tag Replacement"', '"widget-data-dialog-title-edit": "Ear tag replacement"'), '"section-title": "Ear Tag Replacement"', '"section-title": "Ear tag replacement"')::jsonb, "section_description" = 'Ear tag replacement'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_retagging_details_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(section_ui_schema::text, '"section-title": "Farmer Identity"', '"section-title": "Farmer identity"')::jsonb, "section_description" = 'Farmer identity'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_intake_identity_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "Audit Log Details"', '"widget-label": "Audit log details"'), '"widget-label": "Related Model"', '"widget-label": "Related model"'), '"widget-label": "Related Record"', '"widget-label": "Related record"'), '"label": "CREATE"', '"label": "Create"'), '"label": "UPDATE"', '"label": "Update"'), '"label": "DELETE"', '"label": "Delete"'), '"label": "IMPORT"', '"label": "Import"'), '"label": "SYNC"', '"label": "Sync"'), '"widget-label": "User Role"', '"widget-label": "User role"'), '"widget-label": "IP Address"', '"widget-label": "IP address"'), '"widget-data-dialog-title-add": "Add Audit Log Details"', '"widget-data-dialog-title-add": "Add audit log details"'), '"widget-data-dialog-title-edit": "Edit Audit Log Details"', '"widget-data-dialog-title-edit": "Edit audit log details"'), '"section-title": "Audit Log Details"', '"section-title": "Audit log details"')::jsonb, "section_description" = 'Audit log details'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_audit_log_details_section_01';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(section_ui_schema::text, '"section-title": "Farmer Location"', '"section-title": "Farmer location"')::jsonb, "section_description" = 'Farmer location'
WHERE "register_id" = 'f9c6a359-9563-5a43-b0fe-6c7e452037a3' AND "section_id" = 'livestock_farmer_location_section_02';

UPDATE "public"."g2p_register_sections"
SET "section_ui_schema" = replace(replace(replace(replace(replace(replace(replace(replace(replace(section_ui_schema::text, '"widget-label": "Vaccination Details"', '"widget-label": "Vaccination details"'), '"widget-label": "Ear Tag / Secondary Identifier"', '"widget-label": "Ear tag / secondary identifier"'), '"widget-label": "Vaccination Date"', '"widget-label": "Vaccination date"'), '"widget-label": "Next Due Date"', '"widget-label": "Next due date"'), '"widget-label": "Batch / Lot Number"', '"widget-label": "Batch / lot number"'), '"widget-label": "Administered By"', '"widget-label": "Administered by"'), '"widget-data-dialog-title-add": "Add Vaccination Details"', '"widget-data-dialog-title-add": "Add vaccination details"'), '"widget-data-dialog-title-edit": "Edit Vaccination Details"', '"widget-data-dialog-title-edit": "Edit vaccination details"'), '"section-title": "Vaccination Details"', '"section-title": "Vaccination details"')::jsonb, "section_description" = 'Vaccination details'
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08' AND "section_id" = 'livestock_vaccination_details_section_01';

UPDATE "public"."g2p_register_schemas"
SET "search_result_schema" = replace(replace("search_result_schema"::jsonb::text, '"display_label": "Total Livestock"', '"display_label": "Total livestock"'), '"display_label": "Approval Stage"', '"display_label": "Approval stage"')::json
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08';

UPDATE "public"."g2p_register_schemas"
SET "filter_schema" = replace(replace("filter_schema"::jsonb::text, '"display_label": "Approval Stage"', '"display_label": "Approval stage"'), '"display_label": "Source System"', '"display_label": "Source system"')::json
WHERE "register_id" = '997676d3-7008-59f9-b23e-613ad79bbb08';

UPDATE "public"."g2p_register_schemas"
SET "search_result_schema" = replace(replace("search_result_schema"::jsonb::text, '"display_label": "Farmer Name"', '"display_label": "Farmer name"'), '"display_label": "Farmer Code"', '"display_label": "Farmer code"')::json
WHERE "register_id" = 'f9c6a359-9563-5a43-b0fe-6c7e452037a3';

UPDATE "public"."g2p_register_schemas"
SET "search_result_schema" = replace(replace("search_result_schema"::jsonb::text, '"display_label": "Ear Tag"', '"display_label": "Ear tag"'), '"display_label": "Event Type"', '"display_label": "Event type"')::json
WHERE "register_id" = 'a40e4a02-1b82-5b31-89df-71624bd96545';

UPDATE "public"."g2p_register_schemas"
SET "filter_schema" = replace("filter_schema"::jsonb::text, '"display_label": "Event Type"', '"display_label": "Event type"')::json
WHERE "register_id" = 'a40e4a02-1b82-5b31-89df-71624bd96545';

UPDATE "public"."g2p_register_schemas"
SET "search_result_schema" = replace(replace(replace("search_result_schema"::jsonb::text, '"display_label": "Ear Tag"', '"display_label": "Ear tag"'), '"display_label": "Vaccinated On"', '"display_label": "Vaccinated on"'), '"display_label": "Next Due"', '"display_label": "Next due"')::json
WHERE "register_id" = '51c1f6d6-856a-5e2f-84e9-ff5abdc4fb75';

UPDATE "public"."g2p_register_schemas"
SET "search_result_schema" = replace(replace(replace("search_result_schema"::jsonb::text, '"display_label": "Old Ear Tag"', '"display_label": "Old ear tag"'), '"display_label": "New Ear Tag"', '"display_label": "New ear tag"'), '"display_label": "Date of Retagging"', '"display_label": "Date of retagging"')::json
WHERE "register_id" = 'b853f1db-6dd6-5b16-a0d8-25a8524142e6';

UPDATE "public"."g2p_register_schemas"
SET "search_result_schema" = replace(replace(replace("search_result_schema"::jsonb::text, '"display_label": "Ear Tag"', '"display_label": "Ear tag"'), '"display_label": "Event Type"', '"display_label": "Event type"'), '"display_label": "Event Date"', '"display_label": "Event date"')::json
WHERE "register_id" = '76811bf6-07df-5ed4-9466-13b782f627fe';

UPDATE "public"."g2p_register_schemas"
SET "filter_schema" = replace("filter_schema"::jsonb::text, '"display_label": "Event Type"', '"display_label": "Event type"')::json
WHERE "register_id" = '76811bf6-07df-5ed4-9466-13b782f627fe';

UPDATE "public"."g2p_register_schemas"
SET "search_result_schema" = replace(replace(replace("search_result_schema"::jsonb::text, '"display_label": "Ear Tag"', '"display_label": "Ear tag"'), '"display_label": "Event Type"', '"display_label": "Event type"'), '"display_label": "Breeding Date"', '"display_label": "Breeding date"')::json
WHERE "register_id" = '192c08b0-5403-5167-968a-2676d4af2879';

UPDATE "public"."g2p_register_schemas"
SET "filter_schema" = replace("filter_schema"::jsonb::text, '"display_label": "Event Type"', '"display_label": "Event type"')::json
WHERE "register_id" = '192c08b0-5403-5167-968a-2676d4af2879';

UPDATE "public"."g2p_register_definitions"
SET "register_subject" = 'Health events'
WHERE "register_id" = 'a40e4a02-1b82-5b31-89df-71624bd96545';

UPDATE "public"."g2p_register_definitions"
SET "register_subject" = 'Vital events'
WHERE "register_id" = '76811bf6-07df-5ed4-9466-13b782f627fe';

UPDATE "public"."g2p_register_definitions"
SET "register_subject" = 'Breeding events'
WHERE "register_id" = '192c08b0-5403-5167-968a-2676d4af2879';

UPDATE "public"."g2p_register_definitions"
SET "register_subject" = 'Vaccine schedules'
WHERE "register_id" = '5cdf80bf-0cdb-53e4-a4cf-71927f809250';

UPDATE "public"."g2p_register_definitions"
SET "register_subject" = 'Audit logs'
WHERE "register_id" = '6a3699f0-4b17-5d0d-b8b3-4822bfdab7aa';

UPDATE "public"."g2p_register_definitions"
SET "register_subject" = 'Ear tag replacements'
WHERE "register_id" = 'b853f1db-6dd6-5b16-a0d8-25a8524142e6';

UPDATE "public"."g2p_intake_form_definitions"
SET "form_description" = 'Livestock intake'
WHERE "form_id" = 'e92e8be1-207f-518e-99c2-8bc21cc1f112';

UPDATE "public"."registry_languages"
SET "core_translation" = (COALESCE("core_translation"::jsonb, '{}'::jsonb) ||
'{
 "livestock_ingestion_intake": "Livestock ingestion intake",
 "livestock_intake_tab": "Livestock intake",
 "ls_audit_log_details": "Audit log details",
 "ls_breeding_details": "Breeding details",
 "ls_farmer_identity": "Farmer identity",
 "ls_farmer_location": "Farmer location",
 "ls_health_event_details": "Health event details",
 "ls_livestock_record": "Farmer details",
 "ls_retagging_details": "Ear tag replacement",
 "ls_survey_personnel": "Survey personnel",
 "ls_vaccination_details": "Vaccination details",
 "ls_vaccine_schedule_details": "Vaccine schedule details",
 "ls_vital_event_details": "Vital event details"
}'::jsonb)::json
WHERE "language_code" = 'en';
