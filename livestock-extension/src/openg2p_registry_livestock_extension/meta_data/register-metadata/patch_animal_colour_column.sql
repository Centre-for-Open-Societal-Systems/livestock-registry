-- Patch for already-created environments only.
--
-- Adds `colour` (G2PAnimal, models/animal.py) — the animal's coat/plumage
-- colour, a free-text field on the Animal intake section. Added to the model
-- in 9331e08 (2026-09-09) without a matching patch, so every environment whose
-- g2p_register_animals / g2p_register_history_animals / g2p_intake_form_animals
-- tables already existed by then has been missing the column ever since.
--
-- A fresh install picks this up for free from the SQLAlchemy model at
-- table-creation time; an environment whose tables already exist needs it added
-- in place, which is what this does, idempotently (ADD COLUMN IF NOT EXISTS) —
-- same pattern as patch_animal_quantity_column.sql.
--
-- Without it the staff API answers 500 on EVERY intake-form save, not just one
-- that fills the field in: the read-back after the write selects the model's
-- full column list, so it fails on the missing column regardless of the value.
-- Observed on the dev cluster 2026-09-17:
--
--   Error in save_intake_form_submission: asyncpg.exceptions.UndefinedColumnError:
--   column g2p_intake_form_animals.colour does not exist
--
-- Confirmed there that `quantity`, added to the same model two days LATER
-- (1082c40, 2026-09-11), is present in all three tables while `colour` is
-- absent from all three — the difference being that quantity shipped with its
-- patch file and colour did not.

ALTER TABLE g2p_register_animals
    ADD COLUMN IF NOT EXISTS colour VARCHAR;

ALTER TABLE g2p_register_history_animals
    ADD COLUMN IF NOT EXISTS colour VARCHAR;

ALTER TABLE g2p_intake_form_animals
    ADD COLUMN IF NOT EXISTS colour VARCHAR;
