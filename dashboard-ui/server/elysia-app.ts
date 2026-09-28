// HTTP surface of the dashboard. Every route reads the Livestock Registry
// database directly; nothing here serves fixtures or falls back to canned
// numbers, so an empty registry produces empty responses rather than filler.
import { Elysia } from 'elysia'
import cors from '@elysiajs/cors'
import { performance } from 'perf_hooks'
import { CHART_QUERIES, ChartFilters, DYNAMIC_FILTERS, type ChartName } from '@/lib/chart-queries'
import {
  fetchGeoOptions,
  fetchRecordStates,
  fetchRecordsForExport,
  pool,
  resolveGeoFilter,
  testConnection,
  type GeoLevel,
} from '@/lib/db'
import { withGeoCodes } from '@/lib/geo-codes'
import type { Context } from 'elysia'
import { generateCacheKey, getCachedData, setCachedData } from './cache'

// Filterable columns, all on the livestock holding. The queries expose it as `ls`
// at the point the filter fragment is spliced in, so one mapping serves every
// chart.
//
// Geography is compared on the trimmed name because that is how the register
// stores it — there is no lookup key to match on, and a value captured in the
// field can carry incidental whitespace.
const FILTER_COLUMNS: Record<keyof ChartFilters, string> = {
  region: 'TRIM(ls.region)',
  zone: 'TRIM(ls.zone)',
  woreda: 'TRIM(ls.woreda)',
  kebele: 'TRIM(ls.kebele)',
  recordState: 'ls.status',
}

/** Geography filters, coarsest first: each is resolved in the context of the last. */
const GEO_LADDER: GeoLevel[] = ['region', 'zone', 'woreda', 'kebele']

/** Charts whose rows name an administrative level the choropleth needs codes for. */
const GEO_CHART_LEVELS: Partial<Record<ChartName, GeoLevel>> = {
  livestockKeepersByRegion: 'region',
  livestockKeepersByZone: 'zone',
  livestockKeepersByWoreda: 'woreda',
  livestockKeepersByKebele: 'kebele',
}

function buildWhereClause(filters: ChartFilters): { clause: string; values: any[] } {
  const conditions: string[] = []
  const values: any[] = []

  for (const [key, column] of Object.entries(FILTER_COLUMNS)) {
    const value = filters[key as keyof ChartFilters]
    if (!value || value === 'all') continue
    // TRIM on the parameter too, so a stored name and a selected one are compared
    // on the same footing.
    const placeholder = key === 'recordState' ? `$${values.length + 1}` : `TRIM($${values.length + 1})`
    conditions.push(`${column} = ${placeholder}`)
    values.push(value)
  }

  if (conditions.length === 0) return { clause: '', values: [] }
  return { clause: `AND ${conditions.join(' AND ')}`, values }
}

/**
 * Rewrites the geography the UI sends into the names records are stored under.
 *
 * The sidebar and the choropleth both work in boundary P-codes ("ET04"), while a
 * record holds "Oromia". The ladder is walked coarsest first because resolving a
 * zone needs its region: two regions can hold a zone of the same name, and the
 * selected region is what tells them apart.
 */
async function resolveFilters(filters: ChartFilters): Promise<ChartFilters> {
  const resolved: ChartFilters = { ...filters }
  let parentName: string | undefined

  for (const level of GEO_LADDER) {
    const value = filters[level]
    if (!value || value === 'all') {
      // A gap in the ladder ends the chain: a woreda cannot be scoped by a zone
      // that was not selected.
      parentName = undefined
      continue
    }
    resolved[level] = await resolveGeoFilter(level, value, parentName)
    parentName = resolved[level]
  }

  return resolved
}

function prepareChartSql(baseQuery: string, resolved: ChartFilters) {
  const { clause, values } = buildWhereClause(resolved)
  return { sql: baseQuery.replace(DYNAMIC_FILTERS, clause), values }
}

async function executeChartQuery(chartName: string, filters: ChartFilters, resolved: ChartFilters) {
  const cacheKey = generateCacheKey(`chart:${chartName}`, filters)

  const cached = getCachedData<any>(cacheKey)
  if (cached) {
    return { ...cached, fromCache: true }
  }

  const startTime = performance.now()

  try {
    const baseQuery = CHART_QUERIES[chartName as ChartName]
    if (!baseQuery) {
      throw new Error(`Query for chart "${chartName}" not found.`)
    }

    const { sql, values } = prepareChartSql(baseQuery, resolved)
    const { rows } = await pool.query(sql, values)

    // The register stores administrative names, so the boundary code each row
    // needs to tint a shape is attached here rather than selected in SQL.
    const geoLevel = GEO_CHART_LEVELS[chartName as ChartName]
    const data = geoLevel ? await withGeoCodes(geoLevel, rows) : rows

    const result = {
      chartName,
      success: true,
      data,
      error: null,
      executionTime: Math.round(performance.now() - startTime),
    }
    setCachedData(cacheKey, result)
    return result
  } catch (error: any) {
    console.error(`Error executing ${chartName}:`, error)
    return {
      chartName,
      success: false,
      data: [],
      error: error instanceof Error ? error.message : 'Unknown error',
      executionTime: Math.round(performance.now() - startTime),
    }
  }
}

function parseChartFilters(query: Context['query']): ChartFilters {
  return {
    region: (query.region as string) || 'all',
    zone: (query.zone as string) || 'all',
    woreda: (query.woreda as string) || 'all',
    kebele: (query.kebele as string) || 'all',
    recordState: (query.recordState as string) || (query.state as string) || 'all',
  }
}

function jsonToCsv(items: any[]): string {
  if (!items || items.length === 0) return ''
  const replacer = (_key: any, value: any) => (value === null ? '' : value)
  const header = Object.keys(items[0])
  return [
    header.join(','),
    ...items.map(row => header.map(field => JSON.stringify(row[field], replacer)).join(',')),
  ].join('\r\n')
}

export function createElysiaApp(prefix = '/api') {
  return new Elysia({ prefix })
    .use(cors())
    .get('/health', async () => ({
      status: (await testConnection()) ? 'ok' : 'degraded',
      service: 'livestock-dashboard',
      timestamp: new Date().toISOString(),
    }))

    // Options for the sidebar's dropdowns, drawn from the holdings the registry
    // holds so the filters can only offer geography that would return something.
    .get('/filter-options', async ({ set }) => {
      try {
        const [regions, recordStatuses] = await Promise.all([
          fetchGeoOptions('region'),
          fetchRecordStates(),
        ])
        return { regions, recordStatuses }
      } catch (error: any) {
        console.error('API Error fetching filter options:', error)
        set.status = 500
        return {
          message: 'Failed to fetch filter options',
          error: error instanceof Error ? error.message : 'Unknown error',
        }
      }
    })

    // One step of the geography cascade. The caller passes the parent it has
    // selected, as either a P-code or the stored name, and gets that parent's
    // children back.
    .get('/locations', async ({ query, set }) => {
      const steps: Array<{ param: string; parent: GeoLevel; child: GeoLevel; key: string }> = [
        { param: 'woredaId', parent: 'woreda', child: 'kebele', key: 'kebeles' },
        { param: 'zoneId', parent: 'zone', child: 'woreda', key: 'woredas' },
        { param: 'regionId', parent: 'region', child: 'zone', key: 'zones' },
      ]

      try {
        // Finest first, so passing several parameters answers the deepest one
        // asked for rather than whichever happens to be checked first.
        for (const step of steps) {
          const value = query[step.param] as string | undefined
          if (!value || value === 'all') continue
          const parentName = await resolveGeoFilter(step.parent, value)
          return { [step.key]: await fetchGeoOptions(step.child, parentName) }
        }

        set.status = 400
        return { error: 'A valid query parameter (regionId, zoneId, or woredaId) is required.' }
      } catch (error: any) {
        console.error('API Error fetching locations:', error)
        set.status = 500
        return { error: 'An internal server error occurred.' }
      }
    })

    // The rows behind the current view, as CSV.
    .post('/data/export', async ({ body, set }) => {
      try {
        const { filters, format, filename } = (body || {}) as any

        if (!format || !filename) {
          set.status = 400
          return { message: 'Missing required parameters' }
        }
        if (format !== 'csv') {
          set.status = 400
          return { message: 'Unsupported format' }
        }

        const resolved = await resolveFilters((filters || {}) as ChartFilters)
        const { clause, values } = buildWhereClause(resolved)
        const rows = await fetchRecordsForExport(clause, values)

        return new Response(jsonToCsv(rows), {
          status: 200,
          headers: {
            'Content-Type': 'text/csv',
            'Content-Disposition': `attachment; filename="${filename}"`,
          },
        })
      } catch (error: any) {
        console.error('API Export Error:', error)
        set.status = 500
        return {
          message: 'Failed to export data',
          error: error instanceof Error ? error.message : 'Unknown error',
        }
      }
    })

    // Chart data. `charts` selects a subset; without it every panel's query runs.
    .get('/charts', async ({ query, set }) => {
      try {
        const filters = parseChartFilters(query)
        const requested = (query.charts as string | undefined)?.split(',').filter(Boolean)
        const targetCharts = requested?.length ? requested : Object.keys(CHART_QUERIES)

        const resolved = await resolveFilters(filters)
        const resultsArray = await Promise.all(
          targetCharts.map(chartId => executeChartQuery(chartId, filters, resolved))
        )

        const results: Record<string, any> = {}
        let successful = 0
        let failed = 0
        let totalExecutionTime = 0

        resultsArray.forEach(result => {
          results[result.chartName] = result
          totalExecutionTime += result.executionTime || 0
          if (result.success) successful++
          else failed++
        })

        return {
          success: true,
          data: results,
          summary: { total: targetCharts.length, successful, failed, totalExecutionTime },
          filters,
          timestamp: new Date().toISOString(),
        }
      } catch (error: any) {
        console.error('Charts API Error:', error)
        set.status = 500
        return {
          success: false,
          error: 'Failed to fetch chart data',
          message: error instanceof Error ? error.message : 'Unknown error',
        }
      }
    })

    .get('/charts/:chartId', async ({ params, query, set }) => {
      const chartName = params.chartId

      try {
        if (!CHART_QUERIES[chartName as ChartName]) {
          set.status = 404
          return { success: false, error: `Chart query '${chartName}' not found.` }
        }

        const filters = parseChartFilters(query)
        const resolved = await resolveFilters(filters)
        const result = await executeChartQuery(chartName, filters, resolved)

        if (!result.success) {
          set.status = 500
          return { success: false, error: result.error }
        }

        return { success: true, data: result.data, executionTime: result.executionTime }
      } catch (error: any) {
        console.error(`API Error for [${chartName}]:`, error)
        set.status = 500
        return {
          success: false,
          error: error instanceof Error ? error.message : 'An unknown database error occurred',
        }
      }
    })
}
