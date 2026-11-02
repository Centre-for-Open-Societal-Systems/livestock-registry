-- Animal sex as the Master Data LIVESTOCK_SEX codes: MALE / FEMALE / MIXED
-- become SEX_MALE / SEX_FEMALE / SEX_MIXED (the same meaning under the codes
-- of the ETH-OAN list). Covers the register, its history, the intake drafts
-- (saved and pending approval) and the change requests not yet applied, so a
-- record opened, approved or reverted later carries the code the dropdown
-- lists. Farmer gender (the GENDER list) is not touched: change requests are
-- converted only for the Animal and Vital Event registers.
--
-- Anything this misses is still read: services/animal_sex.py converts the old
-- codes on save. Re-runs touch nothing, the old codes are gone.

UPDATE g2p_register_animals SET gender = 'SEX_' || UPPER(TRIM(gender))
WHERE UPPER(TRIM(gender)) IN ('MALE', 'FEMALE', 'MIXED');

UPDATE g2p_register_history_animals SET gender = 'SEX_' || UPPER(TRIM(gender))
WHERE UPPER(TRIM(gender)) IN ('MALE', 'FEMALE', 'MIXED');

UPDATE g2p_intake_form_animals SET gender = 'SEX_' || UPPER(TRIM(gender))
WHERE UPPER(TRIM(gender)) IN ('MALE', 'FEMALE', 'MIXED');

UPDATE g2p_register_vital_events SET offspring_gender = 'SEX_' || UPPER(TRIM(offspring_gender))
WHERE UPPER(TRIM(offspring_gender)) IN ('MALE', 'FEMALE', 'MIXED');

UPDATE g2p_register_history_vital_events SET offspring_gender = 'SEX_' || UPPER(TRIM(offspring_gender))
WHERE UPPER(TRIM(offspring_gender)) IN ('MALE', 'FEMALE', 'MIXED');

UPDATE g2p_intake_form_vital_events SET offspring_gender = 'SEX_' || UPPER(TRIM(offspring_gender))
WHERE UPPER(TRIM(offspring_gender)) IN ('MALE', 'FEMALE', 'MIXED');

-- Change request rows: a JSON array of records. 041a9f79... is the Animal
-- register, 76811bf6... the Vital Event register (g2p_register_definitions).
UPDATE g2p_register_change_request_payloads AS p
SET change_payload = (
  SELECT json_agg(
    CASE WHEN jsonb_typeof(e) = 'object' THEN
      e
      || CASE WHEN UPPER(TRIM(e ->> 'gender')) IN ('MALE', 'FEMALE', 'MIXED')
              THEN jsonb_build_object('gender', 'SEX_' || UPPER(TRIM(e ->> 'gender'))) ELSE '{}'::jsonb END
      || CASE WHEN UPPER(TRIM(e ->> 'offspring_gender')) IN ('MALE', 'FEMALE', 'MIXED')
              THEN jsonb_build_object('offspring_gender', 'SEX_' || UPPER(TRIM(e ->> 'offspring_gender'))) ELSE '{}'::jsonb END
    ELSE e END
    ORDER BY ord)
  FROM jsonb_array_elements(p.change_payload::jsonb) WITH ORDINALITY AS t(e, ord)
)
FROM g2p_register_change_requests AS r
WHERE r.change_request_id = p.change_request_id
  AND r.section_register_id IN ('041a9f79-2142-548a-a15b-a4c76fc9f6f7', '76811bf6-07df-5ed4-9466-13b782f627fe')
  AND json_typeof(p.change_payload) = 'array'
  AND p.change_payload::text ~* '"(offspring_)?gender" *: *" *(male|female|mixed) *"';
