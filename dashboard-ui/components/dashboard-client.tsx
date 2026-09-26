"use client"

import { useState, useEffect, useCallback, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { ArrowLeft, Menu, X, Camera } from "lucide-react"
import { GlobalFiltersSidebar } from "@/components/global-filters-sidebar"
import { ExportDataButton } from "@/components/registry/export-button"
import type { RegistryFilters } from "@/components/registry/registry-data"
import { resolveReturnUrl } from "@/lib/return-url"
import dynamic from "next/dynamic"
import { DashboardSectionSkeleton } from "@/components/ui/dashboard-skeleton"

export default function DashboardClient({
  geoJsonData,
  initialFilters,
}: {
  geoJsonData: any;
  initialFilters?: RegistryFilters;
}) {
  const [filters, setFilters] = useState<RegistryFilters>(initialFilters || {
    region: 'all',
    zone: 'all',
    woreda: 'all',
    kebele: 'all',
    recordState: 'all',
  })

  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen)

  // Where "Back" should land. Resolved on the client because it depends on the
  // returnUrl the staff portal appended when it sent us here.
  const [returnUrl, setReturnUrl] = useState<string | null>(null)
  useEffect(() => {
    setReturnUrl(resolveReturnUrl(window.location.search, document.referrer))
  }, [])

  const goBack = useCallback(() => {
    if (returnUrl) {
      window.location.href = returnUrl
      return
    }
    // Opened directly rather than from the portal, so fall back to history.
    window.history.back()
  }, [returnUrl])

  // P-code -> label, so the active-filter chips can name what is selected. `id` is
  // the registry's stored key for that value, which is what the cascade is walked by.
  const [regionsLookup, setRegionsLookup] = useState<Map<string, { name: string; id: string }>>(new Map())
  const [zonesLookup, setZonesLookup] = useState<Map<string, { name: string; id: string; regionId?: string }>>(new Map())
  const [woredasLookup, setWoredasLookup] = useState<Map<string, { name: string; id: string; zoneId?: string }>>(new Map())

  const setFiltersIfChanged = useCallback((updater: (prev: typeof filters) => typeof filters) => {
    setFilters(prev => {
      const next = updater(prev)
      // shallow compare to avoid rerenders when nothing actually changed
      const changed = Object.keys(prev).some(key => (prev as any)[key] !== (next as any)[key])
      return changed ? next : prev
    })
  }, [])

  const handleMapFilterChange = useCallback((mapFilters: Partial<RegistryFilters>) => {
    setFiltersIfChanged(prev => ({
      ...prev,
      region: mapFilters.region ?? prev.region ?? 'all',
      zone: mapFilters.zone ?? prev.zone ?? 'all',
      woreda: mapFilters.woreda ?? prev.woreda ?? 'all',
      kebele: mapFilters.kebele ?? prev.kebele ?? 'all',
      recordState: mapFilters.recordState ?? prev.recordState,
    }))
  }, [setFiltersIfChanged])

  // Load region lookup once for name resolution in header tags
  useEffect(() => {
    const fetchRegions = async () => {
      try {
        const res = await fetch('/api/filter-options')
        if (!res.ok) return
        const data = await res.json()
        const map = new Map<string, { name: string; id: string }>()
        ;(data?.regions || []).forEach((r: any) => {
          if (!r?.code) return
          map.set(r.code, { name: r.name || r.code, id: r.id })
        })
        setRegionsLookup(map)
      } catch (err) {
        // ignore
      }
    }
    fetchRegions()
  }, [])

  // When region changes, ensure zones lookup is populated for that region code if missing
  useEffect(() => {
    const loadZones = async () => {
      if (filters.region === 'all') return
      // If we already have zones for this region, skip
      if (Array.from(zonesLookup.values()).some(z => z.regionId === regionsLookup.get(filters.region)?.id)) return
      const regionMeta = regionsLookup.get(filters.region)
      const regionParam = regionMeta?.id || filters.region
      try {
        const res = await fetch(`/api/locations?regionId=${encodeURIComponent(regionParam)}`)
        if (!res.ok) return
        const data = await res.json()
        const next = new Map(zonesLookup)
        ;(data?.zones || []).forEach((z: any) => {
          if (!z?.code) return
          next.set(z.code, { name: z.name || z.code, id: z.id, regionId: regionMeta?.id })
        })
        setZonesLookup(next)
      } catch (err) {
        // ignore
      }
    }
    loadZones()
  }, [filters.region, regionsLookup, zonesLookup])

  // When zone changes, ensure woredas lookup is populated for that zone code if missing
  useEffect(() => {
    const loadWoredas = async () => {
      if (filters.zone === 'all') return
      const zoneMeta = zonesLookup.get(filters.zone)
      // If we already have woredas for this zone, skip
      if (zoneMeta && Array.from(woredasLookup.values()).some(w => w.zoneId === zoneMeta.id)) return
      const zoneParam = zoneMeta?.id || filters.zone
      try {
        const res = await fetch(`/api/locations?zoneId=${encodeURIComponent(zoneParam)}`)
        if (!res.ok) return
        const data = await res.json()
        const next = new Map(woredasLookup)
        ;(data?.woredas || []).forEach((w: any) => {
          if (!w?.code) return
          next.set(w.code, { name: w.name || w.code, id: w.id, zoneId: zoneMeta?.id })
        })
        setWoredasLookup(next)
      } catch (err) {
        // ignore
      }
    }
    loadWoredas()
  }, [filters.zone, zonesLookup, woredasLookup])

  const captureElementById = useCallback(async (id: string, prefix: string) => {
    try {
      const target = document.getElementById(id)
      if (!target) return
      const { toPng } = await import("html-to-image")

      // Hide KPI elements if present to capture only charts
      const hidden: Array<{ el: HTMLElement; prev: string }> = []
      target.querySelectorAll<HTMLElement>('[data-kpi="true"], [data-export-control="true"]').forEach(el => {
        hidden.push({ el, prev: el.style.display })
        el.style.display = 'none'
      })

      const dataUrl = await toPng(target, { cacheBust: true })

      // Restore hidden elements
      hidden.forEach(({ el, prev }) => { el.style.display = prev })

      const link = document.createElement("a")
      link.href = dataUrl
      link.download = `${prefix}-${new Date().toISOString().split("T")[0]}.png`
      link.click()
    } catch (err) {
      console.error("Capture failed", err)
    }
  }, [])

  // Display active filters with proper names
  const activeFilterItems = useMemo(() => {
    const filterItems: Array<{ key: string; label: string; value: string }> = [];

    // Location filters - use lookup names, fall back to codes
    if (filters.region !== 'all') {
      const regionName = regionsLookup.get(filters.region)?.name || filters.region
      filterItems.push({ key: 'region', label: 'Region', value: regionName });
    }
    
    if (filters.zone !== 'all') {
      const zoneName = zonesLookup.get(filters.zone)?.name || filters.zone
      filterItems.push({ key: 'zone', label: 'Zone', value: zoneName });
    }
    
    if (filters.woreda !== 'all') {
      const woredaName = woredasLookup.get(filters.woreda)?.name || filters.woreda
      filterItems.push({ key: 'woreda', label: 'Woreda', value: woredaName });
    }
    
    // Other filters
    if (filters.kebele !== 'all') {
      filterItems.push({ key: 'kebele', label: 'Kebele', value: filters.kebele });
    }
    if (filters.recordState !== 'all') {
      filterItems.push({ key: 'recordState', label: 'Record State', value: filters.recordState });
    }
    
    return filterItems;
  }, [filters, regionsLookup, zonesLookup, woredasLookup]);

  const clearFilter = useCallback((filterKey: string) => {
    setFiltersIfChanged(prev => {
      const next = { ...prev };

      // Clear the requested filter
      next[filterKey as keyof typeof prev] = 'all';

      // Cascade clears for dependent children to keep sidebar/dropdowns/map in sync
      if (filterKey === 'region') {
        next.zone = 'all';
        next.woreda = 'all';
        next.kebele = 'all';
      }
      if (filterKey === 'zone') {
        next.woreda = 'all';
        next.kebele = 'all';
      }
      if (filterKey === 'woreda') {
        next.kebele = 'all';
      }

      return next;
    })
  }, [setFiltersIfChanged]);

  return (
    <div id="dashboard-root" className="animate-page-fade max-h-screen overflow-hidden bg-background text-foreground flex flex-col bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background">
      {/* Full Width Header */}
      <div className="w-full relative overflow-hidden bg-[#01215A] text-white py-1 px-4 md:px-6 flex-shrink-0 z-10 shadow-sm">
        {/* Decorative national flag; its hoist edge fades into the ribbon. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute right-0 top-0 hidden h-full w-[240px] bg-[url('/images/ethiopia-flag-wave.svg')] bg-right bg-no-repeat opacity-95 md:block"
          style={{ backgroundSize: 'auto 100%' }}
        />

        {/* Right padding keeps the controls clear of the flag artwork. */}
        <div className="max-w-full grid grid-cols-[auto_1fr_auto] items-center relative z-10 gap-4 md:pr-[110px]">
          <div className="flex items-center">
            <img
              src="/images/ati_small.jpg"
              alt="Ministry of Finance Logo"
              className="h-10 w-10 md:h-12 rounded-full md:w-12 object-contain"
            />
          </div>

          <div className="flex min-w-0 flex-col items-center gap-1">
            <div className="text-center">
              <h1 className="text-lg md:text-xl font-bold text-white">Livestock Registry</h1>
            </div>

            {/* Active Filters Display */}
            {activeFilterItems.length > 0 && (
              <div className="hidden md:flex justify-center px-4 gap-2 flex-wrap">
                {activeFilterItems.map((filter) => (
                  <div
                    key={filter.key}
                    className="bg-white/10 px-3 py-1 rounded-full text-xs font-medium text-white border border-white/20 flex items-center gap-2"
                  >
                    <span>{filter.label}: {filter.value}</span>
                    <button
                      onClick={() => clearFilter(filter.key)}
                      className="hover:bg-white/20 rounded-full p-0.5 transition-colors"
                      aria-label={`Clear ${filter.label} filter`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2 justify-self-end">
            <Button
              variant="outline"
              size="sm"
              onClick={goBack}
              className="border-white/30 bg-[#01215A]/80 text-white backdrop-blur-sm hover:bg-[#01215A] hover:text-white"
            >
              <ArrowLeft className="h-4 w-4 md:mr-2" />
              <span className="hidden md:inline">Back</span>
            </Button>

            <ExportDataButton
              tone="red"
              filters={filters}
              filePrefix="livestock-registry"
              captureTargetId="tab-content-livestock-registry"
            />

            <Button
              variant="outline"
              size="sm"
              className="border-white/30 bg-[#01215A]/80 text-white backdrop-blur-sm hover:bg-[#01215A] hover:text-white"
              onClick={() => captureElementById('tab-content-livestock-registry', 'livestock-registry')}
            >
              <Camera className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex flex-1 min-h-0 max-h-screen">
        {/* Sidebar */}
        <div className={`${isSidebarOpen ? 'w-80' : 'w-0'} flex-shrink-0 transition-all duration-300 ease-in-out border-r border-[#0A2A66] bg-gradient-to-b from-[#00134B] to-[#001042] relative h-full`}>
          <div className={`${isSidebarOpen ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300 h-full max-h-full overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent`}>
            <GlobalFiltersSidebar
              filters={filters}
              onFiltersChange={setFilters}
              isSidebarOpen={isSidebarOpen}
              onSidebarToggle={toggleSidebar}
            />
          </div>

          {/* Sidebar Toggle Button */}
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={`absolute ${isSidebarOpen ? '-right-3' : 'left-2'} top-4 z-50 bg-[#076E7D] text-white rounded-full p-1.5 shadow-lg hover:bg-[#0A8496] transition-all duration-300`}
            aria-label={isSidebarOpen ? "Hide sidebar" : "Show sidebar"}
          >
            {isSidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>

        {/* Main Content */}
        <div
          // Prefer a no-scroll screen on typical laptop heights; fall back to
          // scrolling on shorter viewports so panels are never clipped.
          className="@container flex-1 min-h-0 overflow-y-auto bg-[#F5F8F6] p-3 md:p-4"
        >
          <div id="tab-content-livestock-registry" className="h-full min-h-0">
            <LivestockDashboard
              filters={filters}
              geoJsonData={geoJsonData}
              onMapFilterChange={handleMapFilterChange}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

const LivestockDashboard = dynamic(
  () => import("@/components/livestock-dashboard").then(mod => mod.LivestockDashboard),
  { ssr: false, loading: () => <TabSkeleton /> }
)

function TabSkeleton() {
  return (
    <DashboardSectionSkeleton />
  )
}
