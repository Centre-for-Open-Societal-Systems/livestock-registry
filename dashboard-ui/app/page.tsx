"use client";

import DashboardClient from '@/components/dashboard-client';
import type { RegistryFilters } from '@/components/registry/registry-data';

export const dynamic = "force-dynamic";

export default function Page() {
  // Unfiltered: the dashboard opens on everything the registry holds.
  const initialFilters: RegistryFilters = {
    region: "all",
    zone: "all",
    woreda: "all",
    kebele: "all",
    recordState: "all",
  };

  return (
    <DashboardClient
      geoJsonData={null} // defer map topo to client fetch to keep payload small
      initialFilters={initialFilters}
    />
  );
}
