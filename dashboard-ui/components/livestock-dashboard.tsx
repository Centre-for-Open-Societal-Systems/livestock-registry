"use client"

// Livestock Registry view. Laid out as a single screen with no scrolling, using
// the band grid and panel density of the OpenG2P reference dashboard.
//
// Ported from the reference dashboard's livestock screen, with every panel
// repointed at this registry's own tables. Two panels therefore measure something
// different from their counterparts there: the species mix counts the animals
// this registry has registered rather than reading national census totals, and
// the donut reports recorded herd health rather than land tenure, which a
// livestock holding does not record. Both narrow with the filters, as every panel
// here does.

import { useMemo } from "react"
import { Home, Layers, MapPinned, PawPrint, UserRound, Users } from "lucide-react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { useChartGroupData } from "@/hooks/use-data"
import { MapWhenVisible } from "@/components/lazy/map-when-visible"
import {
  BarList,
  BRIGHT,
  BRIGHT_SOFT,
  DeltaChip,
  EmptyPanel,
  RankList,
  REGISTRY_COLORS,
  RegistryCard,
  RegistryDonut,
  RegistryStat,
  formatCompact,
  formatFull,
} from "@/components/registry/registry-ui"
import {
  RegistryFilters,
  buildTrend,
  monthLabel,
  toNumber,
  useRegistryTrend,
} from "@/components/registry/registry-data"

const CHART_NAMES = [
  "livestockKpis",
  "livestockBySpecies",
  "livestockKeepersByRegion",
  "livestockTopWoredas",
  "herdHealthSplit",
  "registryTrendByMonth",
]

// Keeps the drill-down counts on keepers, the same measure the region choropleth
// is tinted by, instead of the map's default farmer charts.
const LIVESTOCK_CHILD_CHARTS = {
  zones: "livestockKeepersByZone",
  woredas: "livestockKeepersByWoreda",
  kebeles: "livestockKeepersByKebele",
}

// The register's HealthStatusEnum, in the order a reader cares about: sound stock
// first, then the conditions that need attention.
const HEALTH_COLORS: Record<string, string> = {
  HEALTHY: BRIGHT.green,
  SICK: BRIGHT.amber,
  QUARANTINED: BRIGHT.orange,
  INJURED: BRIGHT.violet,
  DECEASED: BRIGHT.crimson,
  Unknown: "#94A3B8",
}

const HEALTH_ORDER = ["HEALTHY", "SICK", "INJURED", "QUARANTINED", "DECEASED"]

/** "UP_TO_DATE" -> "Up to date". Enum values reach the UI unlabelled. */
function humanize(value: string): string {
  const words = String(value || "").replace(/_/g, " ").toLowerCase().trim()
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Unknown"
}

export function LivestockDashboard({
  filters,
  geoJsonData,
  onMapFilterChange,
}: {
  filters: RegistryFilters
  geoJsonData?: any
  onMapFilterChange?: (filters: Record<string, string>) => void
}) {
  const { data, loading, error } = useChartGroupData(CHART_NAMES, filters as any)
  const charts = data?.data || {}

  const kpis = charts.livestockKpis?.[0] || null
  const keepers = toNumber(kpis?.keepers)
  const holdings = toNumber(kpis?.holdings)
  const animals = toNumber(kpis?.animals)
  const femaleKeepers = toNumber(kpis?.female_keepers)
  const speciesTracked = toNumber(kpis?.species_tracked)
  const breedsTracked = toNumber(kpis?.breeds_tracked)
  const woredasReporting = toNumber(kpis?.woredas_reporting)
  const femaleShare = keepers > 0 ? (femaleKeepers / keepers) * 100 : 0

  const trend = useRegistryTrend(charts.registryTrendByMonth)

  // Panels are height-capped in the band grid, so the longest tails are trimmed
  // rather than allowed to overflow their card.
  const speciesItems = useMemo(
    () =>
      (charts.livestockBySpecies || []).slice(0, 7).map((row: any) => ({
        name: row.species,
        value: toNumber(row.animals),
      })),
    [charts.livestockBySpecies]
  )

  const keepersByRegion = useMemo(
    () =>
      (charts.livestockKeepersByRegion || []).map((row: any) => ({
        region: row.region,
        region_code: row.region_code,
        farmers: toNumber(row.farmers),
      })),
    [charts.livestockKeepersByRegion]
  )

  const topWoredas = useMemo(
    () =>
      (charts.livestockTopWoredas || []).slice(0, 8).map((row: any) => ({
        name: row.woreda,
        value: toNumber(row.farmers),
      })),
    [charts.livestockTopWoredas]
  )

  const healthSegments = useMemo(
    () =>
      (charts.herdHealthSplit || [])
        .map((row: any) => ({
          status: String(row.health_status || "Unknown"),
          value: toNumber(row.animals),
        }))
        .filter((row: { value: number }) => row.value > 0)
        .sort((a: { status: string }, b: { status: string }) => {
          const rank = (status: string) => {
            const index = HEALTH_ORDER.indexOf(status)
            return index === -1 ? HEALTH_ORDER.length : index
          }
          return rank(a.status) - rank(b.status)
        })
        .map((row: { status: string; value: number }) => ({
          name: humanize(row.status),
          value: row.value,
          color: HEALTH_COLORS[row.status] || BRIGHT.violet,
        })),
    [charts.herdHealthSplit]
  )

  const healthAnimals = healthSegments.reduce(
    (acc: number, segment: { value: number }) => acc + segment.value,
    0
  )

  // Cumulative registrations reproduce the reference dashboard's climbing area curve.
  const registrationSeries = useMemo(() => {
    let running = 0
    return trend.series.map((point) => {
      running += point.farmers
      return { period: monthLabel(point.period), registered: running }
    })
  }, [trend.series])

  const recentRegistrations = useMemo(() => registrationSeries.slice(-12), [registrationSeries])

  const keeperTrend = buildTrend(trend.series, "farmers", { cumulative: true })
  const animalTrend = buildTrend(trend.series, "animals", { cumulative: true })

  if (error) {
    return (
      <RegistryCard title="Livestock Registry">
        <div className="px-4 pb-5 pt-3 text-[16.5px]" style={{ color: REGISTRY_COLORS.red }}>
          Failed to load registry data: {error}
        </div>
      </RegistryCard>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 @[860px]:grid @[860px]:grid-rows-[auto_auto_minmax(0,1.32fr)_minmax(0,1fr)_auto]">
      {/* Title line */}
      <header className="flex flex-none flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <h2 className="text-[22px] font-bold leading-tight tracking-[-0.3px]" style={{ color: REGISTRY_COLORS.ink }}>
          Livestock Registry
        </h2>
        <p className="text-[17px]" style={{ color: REGISTRY_COLORS.muted }}>
          National Livestock Registry Module
        </p>
      </header>

      {/* Band 1 — KPI ribbon */}
      <section className="grid flex-none grid-cols-2 gap-3 @[640px]:grid-cols-3 @[860px]:grid-cols-[1.11fr_0.85fr_0.92fr_1.15fr_1.05fr_1.02fr]">
        <RegistryStat
          icon={<Users className="h-9 w-9" strokeWidth={2.5} />}
          iconBg={BRIGHT_SOFT.blue}
          iconColor={BRIGHT.blue}
          tint="blue"
          value={formatFull(keepers)}
          label="Livestock Keepers"
          delta={keeperTrend.delta}
          loading={loading}
        />
        <RegistryStat
          icon={<Home className="h-9 w-9" strokeWidth={2.5} />}
          iconBg={BRIGHT_SOFT.green}
          iconColor={BRIGHT.green}
          tint="green"
          value={formatFull(holdings)}
          label="Holdings"
          note={holdings > 0 ? `${(animals / holdings).toFixed(1)} animals each` : undefined}
          loading={loading}
        />
        <RegistryStat
          icon={<PawPrint className="h-9 w-9" strokeWidth={2.5} />}
          iconBg={BRIGHT_SOFT.teal}
          iconColor={BRIGHT.teal}
          tint="teal"
          value={formatCompact(animals)}
          label="Animals Registered"
          delta={animalTrend.delta}
          loading={loading}
        />
        <RegistryStat
          icon={<Layers className="h-9 w-9" strokeWidth={2.5} />}
          iconBg={BRIGHT_SOFT.orange}
          iconColor={BRIGHT.orange}
          tint="peach"
          value={formatFull(speciesTracked)}
          label="Species Tracked"
          note={`${formatFull(breedsTracked)} breeds`}
          loading={loading}
        />
        <RegistryStat
          icon={<UserRound className="h-9 w-9" strokeWidth={2.5} />}
          iconBg={BRIGHT_SOFT.pink}
          iconColor={BRIGHT.pink}
          tint="pink"
          value={`${femaleShare.toFixed(1)}%`}
          label="Women Keepers"
          note={`${formatFull(femaleKeepers)} keepers`}
          loading={loading}
        />
        <RegistryStat
          icon={<MapPinned className="h-9 w-9" strokeWidth={2.5} />}
          iconBg={BRIGHT_SOFT.amber}
          iconColor={BRIGHT.amber}
          tint="amber"
          value={formatFull(woredasReporting)}
          label="Woredas Reporting"
          note="with keepers"
          loading={loading}
        />
      </section>

      {/* Band 2 — map, species mix, herd health */}
      <section className="grid min-h-0 flex-none grid-cols-1 gap-3 @[720px]:grid-cols-2 @[860px]:grid-cols-[2.3fr_1.6fr_2fr]">
        <RegistryCard
          dense
          title="Livestock Keepers by Region"
          subtitle={
            loading
              ? "Loading coverage…"
              : `${formatFull(woredasReporting)} woreda${woredasReporting === 1 ? "" : "s"} reporting · click to drill down`
          }
          className="flex min-h-[260px] flex-col overflow-hidden @[860px]:min-h-0"
          bodyClassName="relative min-h-0 flex-1"
        >
          <MapWhenVisible
            fill
            legendPosition="overlay"
            className="absolute inset-0 flex flex-col"
            minHeight="100%"
            variant="registry"
            popOutTitle="Livestock Keepers by Region"
            valueLabel="keepers"
            valueFormatter={(value: number) => formatCompact(value)}
            childChartKeys={LIVESTOCK_CHILD_CHARTS}
            currentFilters={{
              region: filters.region !== "all" ? filters.region : undefined,
              zone: filters.zone !== "all" ? filters.zone : undefined,
              woreda: filters.woreda !== "all" ? filters.woreda : undefined,
            }}
            onFilterChange={(mapFilters: any) => onMapFilterChange?.(mapFilters)}
            farmerData={keepersByRegion}
            geoJsonData={geoJsonData}
          />
        </RegistryCard>

        <RegistryCard
          dense
          title="Livestock by Species"
          subtitle="Registered animals by species"
          className="flex min-h-[220px] flex-col overflow-hidden @[860px]:min-h-0"
          bodyClassName="flex min-h-0 flex-1 flex-col"
        >
          <BarList
            dense
            items={speciesItems}
            unitLabel="Number of animals"
            formatter={(value) => formatCompact(value)}
            emptyMessage="No animals registered in range"
          />
        </RegistryCard>

        <RegistryCard
          dense
          title="Herd Health"
          subtitle="Registered animals by recorded condition"
          className="flex min-h-[220px] flex-col overflow-hidden @[860px]:min-h-0"
          bodyClassName="flex min-h-0 flex-1 items-center"
        >
          <RegistryDonut
            ringSize={260}
            className="w-full"
            segments={healthSegments}
            centerValue={formatCompact(healthAnimals)}
            centerLabel="Animals"
            totalLabel="Total"
            totalValue={`${formatFull(healthAnimals)} animals`}
            emptyMessage="No health status recorded"
          />
        </RegistryCard>
      </section>

      {/* Band 3 — top woredas, registrations over time */}
      <section className="grid min-h-0 flex-none grid-cols-1 gap-3 @[860px]:grid-cols-[2fr_3.9fr]">
        <RegistryCard
          dense
          title="Top Woredas"
          className="flex min-h-[200px] flex-col overflow-hidden @[860px]:min-h-0"
          bodyClassName="flex min-h-0 flex-1 flex-col"
        >
          <RankList dense items={topWoredas} nameHeader="Woreda" valueHeader="Keepers" />
        </RegistryCard>

        <RegistryCard
          dense
          title="Registrations Over Time"
          subtitle="Cumulative registered livestock keepers"
          actions={keeperTrend.delta ? <DeltaChip delta={keeperTrend.delta} /> : undefined}
          className="flex min-h-[220px] flex-col overflow-hidden @[860px]:min-h-0"
          bodyClassName="min-h-0 flex-1 px-1 pb-1 pt-1"
        >
          {recentRegistrations.length === 0 ? (
            <EmptyPanel message="No registrations in range" className="px-3 pb-3" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={recentRegistrations} margin={{ top: 6, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="livestockRegistrations" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={BRIGHT.blueSoft} stopOpacity={0.38} />
                    <stop offset="100%" stopColor={BRIGHT.blueSoft} stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke={REGISTRY_COLORS.line2} />
                <XAxis
                  dataKey="period"
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                  minTickGap={20}
                  tick={{ fontSize: 9.5, fill: REGISTRY_COLORS.muted }}
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={34}
                  tick={{ fontSize: 9.5, fill: REGISTRY_COLORS.muted }}
                  tickFormatter={(value: number) => formatCompact(value)}
                />
                <Tooltip
                  cursor={{ stroke: REGISTRY_COLORS.line, strokeWidth: 1 }}
                  contentStyle={{
                    borderRadius: 10,
                    border: `1px solid ${REGISTRY_COLORS.line}`,
                    fontSize: 11,
                  }}
                  formatter={(value: any) => [formatFull(toNumber(value)), "Registered keepers"]}
                />
                <Area
                  type="monotone"
                  dataKey="registered"
                  stroke={BRIGHT.blue}
                  strokeWidth={2}
                  fill="url(#livestockRegistrations)"
                  dot={{ r: 1.8, fill: "#fff", stroke: BRIGHT.blue, strokeWidth: 1.4 }}
                  activeDot={{ r: 3.5, fill: BRIGHT.blue, stroke: "#fff", strokeWidth: 1.6 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </RegistryCard>
      </section>

      {/* Source ribbon */}
      <div
        className="flex flex-none items-center gap-2 rounded-xl border bg-white px-4 py-1 text-[14.5px]"
        style={{ borderColor: REGISTRY_COLORS.line, color: REGISTRY_COLORS.muted }}
      >
        <Layers className="h-3.5 w-3.5 flex-none" style={{ color: BRIGHT.teal }} />
        <span className="min-w-0 flex-1 truncate">
          Boundaries: geoBoundaries gbOpen ETH ADM1/ADM3 (CC BY 4.0). Figures count the holdings and animals this
          registry holds; a place the 2021 boundaries do not name is listed but not shaded.
        </span>
      </div>
    </div>
  )
}
