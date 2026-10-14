-- Total Livestock (total_animals) on register Livestock records = the number
-- of their animals in the Animal register. Only ODK records used to get it,
-- so web and File Import records showed it blank. New records are kept up to
-- date by refresh_total_animals (domain_validation_utils.py); this brings the
-- existing ones in line. Re-runs touch only rows whose number differs.
UPDATE g2p_register_livestocks AS l
SET total_animals = c.n
FROM (
  SELECT l2.internal_record_id, count(a.internal_record_id)::int AS n
  FROM g2p_register_livestocks l2
  LEFT JOIN g2p_register_animals a ON a.link_internal_record_id = l2.internal_record_id
  GROUP BY l2.internal_record_id
) AS c
WHERE c.internal_record_id = l.internal_record_id
  AND l.total_animals IS DISTINCT FROM c.n;
