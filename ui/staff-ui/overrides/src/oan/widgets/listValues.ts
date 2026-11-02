// The active values of a Master Data list with their per-value attributes, read
// once per list through /api/master-data/list-values and kept for the page.

export type ListValue = {
    value_id: string;
    value_code: string;
    display?: string;
    attributes?: Record<string, any>;
};

type Handler = (service: string, endpoint: string, method: string, params: Record<string, unknown>) => Promise<any>;

const cache = new Map<string, Promise<ListValue[]>>();

export function listValues(handler: Handler | undefined, listCode: string): Promise<ListValue[]> {
    if (!handler || !listCode) return Promise.resolve([]);
    let pending = cache.get(listCode);
    if (!pending) {
        pending = handler('master-data', 'list-values', 'POST', { list_code: listCode })
            .then((rows) => (Array.isArray(rows) ? rows : []))
            .catch(() => []);
        cache.set(listCode, pending);
        // A failed or empty read is tried again on the next dialog.
        pending.then((rows) => {
            if (!rows.length) cache.delete(listCode);
        });
    }
    return pending;
}

// A stored value may be the value_id or the value_code (lists keep both).
export const matches = (row: ListValue, value: unknown) =>
    value !== undefined && value !== null && value !== '' && (row.value_id === value || row.value_code === value);
