'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import {
    SelectWidget,
    TextInputWidget,
    setValues,
    useBaseWidget,
    useWidgetContext,
} from '@openg2p/registry-widgets';
import { formatAge } from './age';

type Config = Record<string, any>;
type AnimalRow = Record<string, any>;
type Handler = (service: string, endpoint: string, method: string, params: Record<string, unknown>) => Promise<any>;

/*
 * The ear tag of an event row (health, vaccination, vital event, breeding),
 * picked from the animals already saved in this intake form.
 *
 * The platform's dialog cannot list another section's rows, so the column
 * used to be a typed text box. This widget reads the form's animals through
 * the portal's own intake-form endpoint and offers them as a dropdown; when
 * there are none yet (or the dialog is not on an intake form), it falls back
 * to the typed text box. The server still checks that the ear tag is an
 * animal of this submission.
 *
 * Metadata (on the ear tag column):
 *   "widget": "oan-animal-picker",
 *   "widget-autofill": {
 *     "sourceSectionId": "livestock_animal_details_section_01",
 *     "matchField": "ear_tag_id",
 *     "fields": { "species": "species", "age": "age" }   // dialog column <- animal field
 *   }
 * Choosing an animal fills those dialog columns (age from the date of birth,
 * the way the server writes it on save).
 */

const LIST_PREFIXES = ['LIVESTOCK_SPECIES_', 'BREED_', 'LIVESTOCK_'];

// "CATTLE" -> "Cattle", "BREED_LOCAL" -> "Local".
const plain = (code: unknown): string => {
    let text = String(code ?? '').trim();
    if (!text) return '';
    for (const prefix of LIST_PREFIXES) {
        if (text.startsWith(prefix)) {
            text = text.slice(prefix.length);
            break;
        }
    }
    const words = text.replace(/_/g, ' ').toLowerCase();
    return words.charAt(0).toUpperCase() + words.slice(1);
};

const identifierOf = (row: AnimalRow, matchField: string): string =>
    String(row[matchField] || row.secondary_identifier || '').trim();

// The submission id: ?sid= on a new form after its first save, or the path of a reopened draft.
const currentSubmissionId = (): string | null => {
    if (typeof window === 'undefined') return null;
    const sid = new URLSearchParams(window.location.search).get('sid');
    if (sid) return sid;
    const match = window.location.pathname.match(/\/submission\/([0-9a-fA-F-]{36})/);
    return match ? match[1] : null;
};

export function AnimalPickerWidget({ config }: { config: Config }) {
    const dispatch = useDispatch();
    const { dataSourceRequestHandler } = useWidgetContext();
    const { widgetId, value } = useBaseWidget({ config: config as never });
    const autofill = (config['widget-autofill'] || {}) as Config;
    const matchField: string = autofill.matchField || 'ear_tag_id';
    const fields: Record<string, string> = autofill.fields || {};
    const [animals, setAnimals] = useState<AnimalRow[]>([]);
    const lastFilled = useRef<string | null>(null);

    useEffect(() => {
        const submissionId = currentSubmissionId();
        if (!submissionId || !dataSourceRequestHandler) return;
        let cancelled = false;
        (async () => {
            const payload = await (dataSourceRequestHandler as Handler)(
                'intake-form', 'get-intake-form-submission', 'POST', { submission_id: submissionId });
            const sections: any[] = payload?.section_payloads || [];
            const section = sections.find((s) => s.section_id === autofill.sourceSectionId)
                || sections.find((s) => /animal_details/.test(String(s.section_id || '')));
            const rows: AnimalRow[] = (section?.records || []).filter(
                (row: AnimalRow) => identifierOf(row, matchField) && row.record_status !== 'DELETED');
            if (!cancelled) setAnimals(rows);
        })();
        return () => {
            cancelled = true;
        };
        // Read once per dialog: each open mounts a new field.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dataSourceRequestHandler]);

    const options = useMemo(() => {
        const list = animals.map((row) => {
            const id = identifierOf(row, matchField);
            const facts = [plain(row.species), plain(row.breed), plain(row.gender), formatAge(row.date_of_birth)]
                .filter(Boolean)
                .join(', ');
            return { label: facts ? `${id} (${facts})` : id, value: id };
        });
        // An edited row keeps its ear tag even when that animal is no longer listed.
        if (value && !list.some((o) => o.value === value)) list.unshift({ label: String(value), value: String(value) });
        return list;
    }, [animals, matchField, value]);

    // Fill the dialog's own columns (Species, Age) from the chosen animal.
    useEffect(() => {
        const columnKey = String(config['column-key'] || '');
        if (!value || value === lastFilled.current || !widgetId.includes('-dlg-') || !widgetId.endsWith(columnKey)) return;
        const animal = animals.find((row) => identifierOf(row, matchField) === value);
        if (!animal) return;
        const prefix = widgetId.slice(0, widgetId.length - columnKey.length);
        const updates: Record<string, unknown> = {};
        for (const [column, source] of Object.entries(fields)) {
            const filled = source === 'age' ? formatAge(animal.date_of_birth) || animal.age : animal[source];
            if (filled !== undefined && filled !== null && filled !== '') updates[prefix + column] = filled;
        }
        lastFilled.current = String(value);
        if (Object.keys(updates).length) dispatch(setValues(updates));
    }, [animals, config, dispatch, fields, matchField, value, widgetId]);

    if (!options.length) {
        return <TextInputWidget config={{ ...config, widget: 'text' } as never} />;
    }
    return (
        <SelectWidget
            config={{ ...config, widget: 'select', 'widget-data-source': { type: 'static', options } } as never}
        />
    );
}
