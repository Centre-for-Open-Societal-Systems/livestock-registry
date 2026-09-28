-- Patch for already-created environments only.
--
-- ear_tag_id on g2p_register_animals used to be NOT NULL for every species.
-- It no longer is: poultry (chicken, duck, ...) and beehive animals have no
-- ear to attach a tag to, so they now identify by secondary_identifier
-- (leg band, wing tag, hive number, RFID, ...) instead — see
-- G2PRegisterDomainServiceAnimal._EAR_TAG_EXEMPT_SPECIES and
-- _validate_identifier_required, which enforce "one of the two, which one
-- depends on species" in the domain service now that the DB no longer can.
--
-- A fresh install picks this up for free from the SQLAlchemy model
-- (models/animal.py, G2PRegisterAnimal) at table-creation time; an
-- environment whose g2p_register_animals table already exists needs the
-- constraint dropped in place, which is what this does. DROP NOT NULL is a
-- no-op (not an error) when the column is already nullable, so this is safe
-- to re-run — same idempotency approach as the other patch_*.sql files here.

ALTER TABLE g2p_register_animals
    ALTER COLUMN ear_tag_id DROP NOT NULL;
