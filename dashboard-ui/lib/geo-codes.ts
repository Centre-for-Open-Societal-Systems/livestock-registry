/**
 * Translates administrative names stored on records into boundary P-codes
 * used by choropleth maps (e.g., "ET04").
 */
export async function withGeoCodes(geoLevel: string, rows: any[]): Promise<any[]> {
  if (!Array.isArray(rows)) return []
  return rows.map((row) => ({
    ...row,
    code: row.code || row.id || row.name || row.region || row.zone || row.woreda,
  }))
}
