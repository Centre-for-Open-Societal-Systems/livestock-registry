// SQL behind the Livestock Registry dashboard.

export interface ChartFilters {
  region?: string
  zone?: string
  woreda?: string
  kebele?: string
  recordState?: string
}

export const DYNAMIC_FILTERS = '--- DYNAMIC_FILTERS ---'

const SCOPE = `
  WITH scope AS (
    SELECT
      ls.internal_record_id,
      ls.farmer_uuid,
      ls.region,
      ls.zone,
      ls.woreda,
      ls.kebele,
      ls.status,
      an.animal_id,
      an.species,
      an.breed,
      an.health_status,
      COALESCE(an.created_at::date, ls.created_at::date) AS recorded_on
    FROM g2p_register_livestocks ls
    LEFT JOIN g2p_register_animals an
      ON an.link_internal_record_id = ls.internal_record_id
     AND an.record_status = 'ACTIVE'
    WHERE ls.record_status = 'ACTIVE'
      ${DYNAMIC_FILTERS}
  )
`

function keepersByLevel(level: 'region' | 'zone' | 'woreda' | 'kebele'): string {
  return `
    ${SCOPE}
    SELECT
      COALESCE(NULLIF(TRIM(av.value_display), ''), s.${level}, 'Unknown') AS ${level},
      av.value_code AS ${level}_code,
      COUNT(DISTINCT s.farmer_uuid) AS farmers,
      COUNT(DISTINCT s.animal_id) AS animal_count
    FROM scope s
    LEFT JOIN g2p_attribute_values av ON av.value_id = s.${level}
    GROUP BY 1, 2
    ORDER BY farmers DESC
  `
}

export const CHART_QUERIES = {
  livestockKpis: `
    ${SCOPE}
    SELECT
      COUNT(DISTINCT s.internal_record_id) AS holdings,
      COUNT(DISTINCT s.farmer_uuid) AS keepers,
      COUNT(DISTINCT s.animal_id) AS animals,
      COUNT(DISTINCT s.species) AS species_count,
      COUNT(DISTINCT s.woreda) AS woredas_reporting
    FROM scope s
  `,

  livestockBySpecies: `
    ${SCOPE}
    SELECT
      COALESCE(NULLIF(TRIM(av.value_display), ''), s.species, 'Unknown') AS species,
      COUNT(s.animal_id) AS animals,
      COUNT(DISTINCT s.farmer_uuid) AS keepers
    FROM scope s
    LEFT JOIN g2p_attribute_values av ON av.value_id = s.species
    WHERE s.species IS NOT NULL
    GROUP BY 1
    ORDER BY animals DESC
  `,

  livestockKeepersByRegion: keepersByLevel('region'),
  livestockKeepersByZone: keepersByLevel('zone'),
  livestockKeepersByWoreda: keepersByLevel('woreda'),
  livestockKeepersByKebele: keepersByLevel('kebele'),

  livestockTopWoredas: `
    ${SCOPE}
    SELECT
      COALESCE(NULLIF(TRIM(av.value_display), ''), s.woreda, 'Unknown') AS woreda,
      av.value_code AS woreda_code,
      COUNT(DISTINCT s.farmer_uuid) AS farmers,
      COUNT(s.animal_id) AS animals
    FROM scope s
    LEFT JOIN g2p_attribute_values av ON av.value_id = s.woreda
    WHERE s.woreda IS NOT NULL
    GROUP BY 1, 2
    ORDER BY farmers DESC
    LIMIT 8
  `,

  herdHealthSplit: `
    ${SCOPE}
    SELECT
      COALESCE(NULLIF(TRIM(av.value_display), ''), s.health_status, 'Healthy') AS health_status,
      COUNT(s.animal_id) AS count
    FROM scope s
    LEFT JOIN g2p_attribute_values av ON av.value_id = s.health_status
    GROUP BY 1
    ORDER BY count DESC
  `,

  registryTrendByMonth: `
    ${SCOPE}
    SELECT
      TO_CHAR(DATE_TRUNC('month', s.recorded_on), 'YYYY-MM') AS period,
      COUNT(DISTINCT s.farmer_uuid) AS farmers,
      COUNT(DISTINCT s.internal_record_id) AS holdings,
      COUNT(s.animal_id) AS animals
    FROM scope s
    WHERE s.recorded_on IS NOT NULL
    GROUP BY 1
    ORDER BY 1
  `,
} as const

export type ChartName = keyof typeof CHART_QUERIES
