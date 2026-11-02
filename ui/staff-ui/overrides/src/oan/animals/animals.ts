// Animals page (SRS LR-24): every registered animal, searched and filtered,
// with a bulk Health / Vaccination Status update.
//
// The Animal register is a table of each Livestock record, so the platform
// has no page for it, but its backend search works on it like on any
// register. The list reads that search; a bulk update is sent as ordinary
// change requests on the Livestock records, one per record, so it goes
// through the same approval, history and audit as a single edit.

import { withCsrfHeaders } from '@/shared/utils/csrf';

export const LIVESTOCK_REGISTER = '997676d3-7008-59f9-b23e-613ad79bbb08';
export const ANIMAL_REGISTER = '041a9f79-2142-548a-a15b-a4c76fc9f6f7';
export const ANIMAL_TAB = 'livestock_animal_tab';
export const ANIMAL_SECTION = 'livestock_animal_details_section_01';

// The columns of the Livestock Details section. A change request may carry only
// a section's own fields (the platform refuses others with REQ-VAL-001), and
// each changed row carries all of them so the section's checks still pass.
const SECTION_FIELDS = [
    'internal_record_id', 'link_internal_record_id', 'ear_tag_id', 'secondary_identifier', 'species', 'breed',
    'quantity', 'weight', 'date_of_birth', 'age', 'gender', 'health_status', 'vaccination_status', 'registration_date',
];

export type AnimalRow = {
    id: string;
    link: string;
    holding: string;
    tag: string;
    species: string;
    breed: string;
    gender: string;
    health: string;
    vaccination: string;
};

export type ListValue = { value_code: string; value_id: string; value_display: string };

export type BulkChange = { health_status?: string; vaccination_status?: string };

export type BulkResult = { requests: number; animals: number; skipped: number; failed: string[] };

export async function postJson(path: string, body: unknown): Promise<{ ok: boolean; json: any }> {
    const res = await fetch(path, {
        method: 'POST',
        credentials: 'include',
        headers: withCsrfHeaders('POST', { 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
    });
    const json = await res.json().catch(() => ({}));
    return { ok: res.ok, json };
}

// A Master Data list, for the filter and bulk-update choices and the labels.
export async function listValues(attributeId: string): Promise<ListValue[]> {
    const { ok, json } = await postJson('/api/attributes/values', { attribute_id: attributeId });
    return ok && Array.isArray(json) ? json : [];
}

export function toAnimalRow(record: any): AnimalRow {
    const fields: Record<string, string> = {};
    for (const field of record?.display_fields || []) fields[field.field_name] = field.value ?? '';
    return {
        id: record.internal_record_id,
        link: record.link_internal_record_id,
        holding: record.link_foundational_id || '',
        tag: fields.ear_tag_id || fields.secondary_identifier || '',
        species: fields.species || '',
        breed: fields.breed || '',
        gender: fields.gender || '',
        health: fields.health_status || '',
        vaccination: fields.vaccination_status || '',
    };
}

const isDeceased = (value: unknown) => String(value || '').trim().toUpperCase() === 'DECEASED';

// One change request per Livestock record, holding the chosen animals' rows with
// only the statuses changed. A deceased animal is left out: its status comes
// from the mortality event, not from an edit.
export async function bulkUpdate(animals: AnimalRow[], change: BulkChange): Promise<BulkResult> {
    const result: BulkResult = { requests: 0, animals: 0, skipped: 0, failed: [] };
    const byHolding = new Map<string, Set<string>>();
    for (const animal of animals) {
        if (!byHolding.has(animal.link)) byHolding.set(animal.link, new Set());
        byHolding.get(animal.link)!.add(animal.id);
    }
    for (const [link, wanted] of byHolding) {
        const label = animals.find((a) => a.link === link)?.holding || link;
        try {
            const section = await postJson('/api/register/section-data', {
                register_id: LIVESTOCK_REGISTER, internal_record_id: link, section_register_id: ANIMAL_REGISTER, page_size: 500,
            });
            const rows: any[] = Array.isArray(section.json) ? section.json : [];
            const changes = [];
            for (const row of rows) {
                if (!wanted.has(row.internal_record_id)) continue;
                if (isDeceased(row.health_status)) {
                    result.skipped += 1;
                    continue;
                }
                const changed: Record<string, unknown> = { edit_action: 'UPDATE' };
                for (const key of SECTION_FIELDS) if (key in row) changed[key] = row[key];
                changed.link_internal_record_id = changed.link_internal_record_id || link;
                Object.assign(changed, change);
                changes.push(changed);
            }
            if (!changes.length) continue;
            const created = await postJson('/api/change-request/create', {
                register_id: LIVESTOCK_REGISTER, register_mnemonic: 'Livestock', section_register_id: ANIMAL_REGISTER,
                tab_id: ANIMAL_TAB, section_id: ANIMAL_SECTION, internal_record_id: link, section_records: changes,
            });
            const message = created.json?.statusText || created.json?.errors?.[0]?.message;
            if (!created.ok || !created.json?.change_request_id) {
                result.failed.push(`${label}: ${message || 'request failed'}`);
            } else {
                result.requests += 1;
                result.animals += changes.length;
            }
        } catch (error) {
            result.failed.push(`${label}: ${error instanceof Error ? error.message : 'request failed'}`);
        }
    }
    return result;
}
