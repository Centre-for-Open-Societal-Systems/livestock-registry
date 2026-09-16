-- Patch for already-created environments only.
--
-- intake_tab_section_3 (the read-only Farmer Details profile card, schema
-- 997676d3-7008-59f9-b23e-613ad79bbb08) was dropped from the livestock
-- intake form's tab-section list -- see the comment in
-- g2p_intake_form_ui_tab_sections.sql for why.
--
-- A fresh install picks this up for free: the row is simply never inserted.
-- An environment that already ran the old seed still has it, and nothing
-- short of an explicit delete removes an already-seeded row -- that INSERT
-- list has no ON CONFLICT handling, so re-seeding a changed list doesn't
-- retract rows that used to be in it. DELETE is a no-op when the row is
-- already gone, so this is safe to re-run -- same idempotency approach as
-- the other patch_*.sql files here.

DELETE FROM g2p_intake_form_ui_tab_sections
WHERE tab_section_id = 'intake_tab_section_3';
