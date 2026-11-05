# Farmer lookup: the first intake section

Every intake form of the Livestock registry starts with one section, **Farmer lookup**
(section id and mnemonic `livestock_farmer_lookup`), on the Livestock Intake form. It holds exactly two fields:

| Field | Rule |
| --- | --- |
| Farmer ID | Required. FR- followed by 12 digits. |
| Fayda ID (FAN or FIN) | Required. A 16-digit FAN (spaces allowed) or a 12-digit FIN. |

There is no FIN display, no Verify with Fayda button and no Farmer reference status on the
intake (decision of 2026-10-28: Crop Sown and Livestock do not use eSignet). 

## How it works

- `livestock-extension/src/openg2p_registry_livestock_extension/meta_data/zz-oan/10_farmer_lookup.sql` creates the section and binds it first on
  every intake tab. The folder sorts after `register-metadata/`, and the seed applies every
  file under `meta_data/` in sorted path order, so this file runs after the older identity
  overlays on every deploy and replaces what they re-apply. It is idempotent and safe on an
  upgrade; no fresh install is needed.
- The old intake identity section (livestock_intake_identity_section_01) stays in the database but is no longer bound to an
  intake tab. Its bindings are removed by their explicit ids each deploy, because the base
  binding file re-adds them.
- The Fayda ID field writes the data key `fayda_id`, which is not a stored column. The domain
  field rules (`register_domain/services/field_rules.py`, `split_fayda_id`) run before the row
  is written and store it as `fayda_fan_id` (16 digits) or `fayda_fin` (12 digits), clearing
  the other. Stored data, deduplication and the Farmer reference lookup keep the two fields.
- The ODK and DCI templates put the farmer identity block under `livestock_farmer_lookup`.

## Known limitation

A saved draft reopens with the Fayda ID field empty, because the stored value lives in the
FAN or FIN column. The stored value is kept; the field is required, so the officer types it
again before moving on.
