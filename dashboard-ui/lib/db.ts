// Connection to the Crop Sown Registry database — the same database the Staff
// Portal's API writes to. Everything the dashboard displays is read from here,
// and nothing here writes.
import { Pool } from 'pg'

export const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT || '5432'),
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  // A dashboard load runs one query per panel in parallel, so the ceiling is set
  // just above that. It stays deliberately small: this database is shared with
  // the registry's own services against a 100-connection server.
  max: 10,
  idleTimeoutMillis: 30000,
  // Fail fast rather than hanging a page load when the server has no slots left.
  connectionTimeoutMillis: 5000,
  keepAlive: true,
})

/** Lookup levels whose keys the registry stores on a crop sown record. */
export type GeoLevel = 'region' | 'zone' | 'woreda' | 'kebele'

/**
 * Turns a lookup P-code into the key the register actually stores.
 *
 * Records hold `region = 'REGION_ET07'` while the map and the sidebar both speak
 * the bare P-code `ET07` (that is what the boundary files carry). g2p_attribute_values
 * holds both, so it is the translator. Anything already in stored form, or absent
 * from the lookup, is passed through untouched so a filter can never silently
 * widen to "everything".
 */
export async function resolveGeoValueId(level: GeoLevel, code: string, parentName?: string): Promise<string> {
  const { rows } = await pool.query(
    `SELECT value_id FROM g2p_attribute_values WHERE attribute_id = $1 AND value_code = $2 LIMIT 1`,
    [level, code]
  )
  return rows[0]?.value_id ?? code
}
export const resolveGeoFilter = resolveGeoValueId


/**
 * The values one lookup level offers, as {code, name} for the dropdowns.
 *
 * `parent` narrows to the children of a stored parent key, which is how the
 * region -> zone -> woreda -> kebele cascade is walked. Kebeles are keyed to their
 * woreda in the same way, so no level needs special handling.
 */
export async function fetchGeoOptions(level: GeoLevel, parentValueId?: string) {
  const params: string[] = [level]
  let where = 'attribute_id = $1'

  if (parentValueId) {
    params.push(parentValueId)
    where += ` AND parent_value_id = $2`
  }

  const { rows } = await pool.query(
    `SELECT value_id AS id, value_code AS code, value_display AS name
       FROM g2p_attribute_values
      WHERE ${where}
      ORDER BY sort_order, value_display`,
    params
  )
  return rows
}

/**
 * Approval states actually present on live records.
 *
 * Taken from the records rather than from the APPROVAL_STATUS lookup so the
 * filter only ever offers states that would return something. `code` is the
 * stored key, which is what the record is filtered on directly — unlike
 * geography, there is no second code system to translate from.
 */
export async function fetchRecordStates() {
  const { rows } = await pool.query(`
    SELECT
      cs.status AS code,
      COALESCE(NULLIF(TRIM(av.value_display), ''), cs.status) AS name,
      COUNT(*) AS count
    FROM g2p_register_crop_sowns cs
    LEFT JOIN g2p_attribute_values av ON av.value_id = cs.status
    WHERE cs.record_status = 'ACTIVE'
      AND cs.status IS NOT NULL
      -- Intermediate approval-workflow states are not offered as analytics
      -- filters; only the final/actionable states are shown.
      AND cs.status NOT IN (
        'APPROVAL_STATUS_APPROVAL_LEVEL_1',
        'APPROVAL_STATUS_APPROVAL_LEVEL_2'
      )
    GROUP BY 1, 2
    ORDER BY count DESC, name
  `)
  return rows
}

/**
 * The registry rows behind the current view, one line per sown plot, for CSV
 * export. Filters are applied by the caller as a compiled WHERE fragment so
 * export and the charts narrow to exactly the same set.
 */
export async function fetchRecordsForExport(whereClause: string, values: any[]) {
  const { rows } = await pool.query(
    `
    SELECT
      cs.functional_record_id      AS record_id,
      cs.farmer_id,
      cs.farmer_name,
      COALESCE(reg.value_display, cs.region)     AS region,
      COALESCE(zon.value_display, cs.zone)       AS zone,
      COALESCE(wor.value_display, cs.woreda)     AS woreda,
      COALESCE(keb.value_display, cs.kebele)     AS kebele,
      COALESCE(sea.value_display, cs.season)     AS season,
      COALESCE(sta.value_display, cs.status)     AS status,
      cs.production_year,
      cs.lifecycle_stage,
      COALESCE(com.value_display, sw.commodity)  AS commodity,
      COALESCE(own.value_display, sw.ownership_type) AS ownership_type,
      sw.area_sown,
      sw.land_area,
      sw.unit,
      sw.sowing_date
    FROM g2p_register_crop_sowns cs
    JOIN g2p_register_sowings sw
      ON sw.link_internal_record_id = cs.internal_record_id
     AND sw.record_status = 'ACTIVE'
    LEFT JOIN g2p_attribute_values reg ON reg.value_id = cs.region
    LEFT JOIN g2p_attribute_values zon ON zon.value_id = cs.zone
    LEFT JOIN g2p_attribute_values wor ON wor.value_id = cs.woreda
    LEFT JOIN g2p_attribute_values keb ON keb.value_id = cs.kebele
    LEFT JOIN g2p_attribute_values sea ON sea.value_id = cs.season
    LEFT JOIN g2p_attribute_values sta ON sta.value_id = cs.status
    LEFT JOIN g2p_attribute_values com ON com.value_id = sw.commodity
    LEFT JOIN g2p_attribute_values own ON own.value_id = sw.ownership_type
    WHERE cs.record_status = 'ACTIVE'
      ${whereClause}
    ORDER BY cs.created_at DESC, cs.functional_record_id
    `,
    values
  )
  return rows
}

/** Whether the registry database is reachable, for /health. */
export async function testConnection(): Promise<boolean> {
  try {
    const client = await pool.connect()
    try {
      await client.query('SELECT 1')
      return true
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('Registry database connection failed:', error)
    return false
  }
}
