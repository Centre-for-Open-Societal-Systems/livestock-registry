'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    SelectWidget,
    TextInputWidget,
    setDataSource,
    setValues,
    useBaseWidget,
    useWidgetContext,
    type WidgetRootState,
} from '@openg2p/registry-widgets';
import { formatAge } from './age';
import { dialogSiblingId } from './dialog';

type Config = Record<string, any>;
type AnimalRow = Record<string, any>;
type Handler = (service: string, endpoint: string, method: string, params: Record<string, unknown>) => Promise<any>;

/*
 * The ear tag of an event row (health, vaccination, vital event, breeding),
 * picked from the animals already saved in this intake form.
 *
 * The platform's dialog cannot list another section's rows, so the column
 * used to be a typed text box. This widget offers the animals as a dropdown,
 * read through the portal's own endpoints: on an intake form, the animals
 * saved in that submission; on a registered Livestock record (its Edit
 * dialogs, which raise a change request), the record's animals. When there
 * are none yet, it falls back to the typed text box. The server still checks
 * that the ear tag is an animal of the submission or the holding.
 *
 * Metadata (on the ear tag column):
 *   "widget": "oan-animal-picker",
 *   "widget-autofill": {
 *     "sourceSectionId": "livestock_animal_details_section_01",   // intake form
 *     "subjectRegisterId": "<Livestock register id>",              // record page
 *     "sourceRegisterId": "<Animal register id>",
 *     "matchField": "ear_tag_id",
 *     "fields": { "species": "species", "age": "age" }   // dialog column <- animal field
 *   },
 *   "widget-option-filter": [                              // optional: which animals are listed
 *     { "field": "health_status", "operator": "notIn", "value": ["DECEASED"] },
 *     { "field": "gender", "operator": "in", "value": ["SEX_FEMALE"],
 *       "when": { "field": "event_type", "operator": "equals", "value": "BIRTH" } }
 *   ]
 * Choosing an animal fills those dialog columns (age from the date of birth,
 * the way the server writes it on save). A filter compares an animal field;
 * its "when" compares a column of the dialog row, and the list follows that
 * column as it changes.
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

type Condition = { field: string; operator: 'equals' | 'notEquals' | 'in' | 'notIn'; value: unknown };
type OptionFilter = Condition & { when?: Condition };

const holds = (actual: unknown, { operator, value }: Condition): boolean => {
    const text = String(actual ?? '').trim().toUpperCase();
    const wanted = (Array.isArray(value) ? value : [value]).map((v) => String(v ?? '').trim().toUpperCase());
    if (operator === 'equals' || operator === 'in') return wanted.includes(text);
    if (operator === 'notEquals' || operator === 'notIn') return !wanted.includes(text);
    return true;
};

const identifierOf = (row: AnimalRow, matchField: string): string =>
    String(row[matchField] || row.secondary_identifier || '').trim();

// The submission id: ?sid= on a new form after its first save, or the path of a reopened draft.
const currentSubmissionId = (): string | null => {
    if (typeof window === 'undefined') return null;
    if (!window.location.pathname.includes('/intake-form/')) return null;
    const sid = new URLSearchParams(window.location.search).get('sid');
    if (sid) return sid;
    const match = window.location.pathname.match(/\/submission\/([0-9a-fA-F-]{36})/);
    return match ? match[1] : null;
};

// The internal id of a registered record page: /register/<type>/<id>.
const currentRecordId = (): string | null => {
    if (typeof window === 'undefined') return null;
    const match = window.location.pathname.match(/\/register\/[^/]+\/([0-9a-fA-F-]{36})(?:\/|$)/);
    return match ? match[1] : null;
};

async function loadAnimals(handler: Handler, autofill: Config): Promise<AnimalRow[]> {
    const submissionId = currentSubmissionId();
    if (submissionId) {
        const payload = await handler('intake-form', 'get-intake-form-submission', 'POST', { submission_id: submissionId });
        // No sections at all is a failed read (an expired login), not a form without animals.
        if (!Array.isArray(payload?.section_payloads)) throw new Error('intake form not loaded');
        const sections: any[] = payload.section_payloads;
        const section = sections.find((s) => s.section_id === autofill.sourceSectionId)
            || sections.find((s) => /animal_details/.test(String(s.section_id || '')));
        return section?.records || [];
    }
    const recordId = currentRecordId();
    if (recordId && autofill.subjectRegisterId && autofill.sourceRegisterId) {
        const rows = await handler('register', 'section-data', 'POST', {
            register_id: autofill.subjectRegisterId,
            internal_record_id: recordId,
            section_register_id: autofill.sourceRegisterId,
            page_size: 500,
        });
        if (!Array.isArray(rows)) throw new Error('record animals not loaded');
        return rows;
    }
    return [];
}

export function AnimalPickerWidget({ config }: { config: Config }) {
    const dispatch = useDispatch();
    const { dataSourceRequestHandler } = useWidgetContext();
    const { widgetId, value } = useBaseWidget({ config: config as never });
    const autofill = (config['widget-autofill'] || {}) as Config;
    const matchField: string = autofill.matchField || 'ear_tag_id';
    const fields: Record<string, string> = autofill.fields || {};
    const columnKey = String(config['column-key'] || '');
    const filtersKey = JSON.stringify(config['widget-option-filter'] || []);
    const filters = useMemo(() => JSON.parse(filtersKey) as OptionFilter[], [filtersKey]);
    // The dialog row's columns the filters' "when" compare, read as one string
    // so the list follows them and nothing else.
    const whenIds = useMemo(
        () => filters.map((f) => (f.when ? dialogSiblingId(widgetId, columnKey, f.when.field) : null)),
        [columnKey, filters, widgetId]);
    const whenKey = useSelector((state: WidgetRootState) =>
        JSON.stringify(whenIds.map((id) => (id ? state.widget?.values?.[id] ?? null : null))));
    const [animals, setAnimals] = useState<AnimalRow[]>([]);
    const [loaded, setLoaded] = useState(false);
    const [failed, setFailed] = useState(false);
    const lastFilled = useRef<string | null>(null);

    useEffect(() => {
        if (!dataSourceRequestHandler) return;
        let cancelled = false;
        (async () => {
            try {
                const rows = (await loadAnimals(dataSourceRequestHandler as Handler, autofill)).filter(
                    (row: AnimalRow) => identifierOf(row, matchField) && row.record_status !== 'DELETED');
                if (!cancelled) {
                    setAnimals(rows);
                    setLoaded(true);
                }
            } catch {
                if (!cancelled) setFailed(true);
            }
        })();
        return () => {
            cancelled = true;
        };
        // Read once per dialog: each open mounts a new field.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dataSourceRequestHandler]);

    const options = useMemo(() => {
        const whenValues = JSON.parse(whenKey) as unknown[];
        const active = filters.filter((f, i) => !f.when || holds(whenValues[i], f.when));
        const listed = animals.filter((row) => active.every((f) => holds(row[f.field], f)));
        const list = listed.map((row) => {
            const id = identifierOf(row, matchField);
            const facts = [plain(row.species), plain(row.breed), plain(row.gender), formatAge(row.date_of_birth)]
                .filter(Boolean)
                .join(', ');
            return { label: facts ? `${id} (${facts})` : id, value: id };
        });
        // An edited row keeps its ear tag even when that animal is no longer listed.
        if (value && !list.some((o) => o.value === value)) list.unshift({ label: String(value), value: String(value) });
        return list;
    }, [animals, filters, matchField, value, whenKey]);

    // The platform's select reads its options from the store and loads a static
    // list only once, so the filtered list is written there whenever it changes.
    useEffect(() => {
        if (loaded && animals.length) dispatch(setDataSource({ widgetId, data: options }));
    }, [animals.length, dispatch, loaded, options, widgetId]);

    // Fill the dialog's own columns (Species, Age) from the chosen animal.
    useEffect(() => {
        if (!value || value === lastFilled.current) return;
        const animal = animals.find((row) => identifierOf(row, matchField) === value);
        if (!animal) return;
        const updates: Record<string, unknown> = {};
        for (const [column, source] of Object.entries(fields)) {
            const target = dialogSiblingId(widgetId, config['column-key'], column);
            const filled = source === 'age' ? formatAge(animal.date_of_birth) || animal.age : animal[source];
            if (target && filled !== undefined && filled !== null && filled !== '') updates[target] = filled;
        }
        lastFilled.current = String(value);
        if (Object.keys(updates).length) dispatch(setValues(updates));
    }, [animals, config, dispatch, fields, matchField, value, widgetId]);

    // No animals saved yet: the typed text box. Animals but none passing the
    // filters (no female for a birth): an empty list, not a free text box.
    // The animals could not be read (an expired login): the text box, saying so.
    if (!animals.length) {
        return (
            <>
                <TextInputWidget config={{ ...config, widget: 'text' } as never} />
                {failed && (
                    <p className="mt-1 text-sm text-red-600" role="alert">
                        This form&apos;s animals could not be loaded. Refresh the page (you may need to log in again),
                        or type the ear tag.
                    </p>
                )}
            </>
        );
    }
    return (
        <SelectWidget
            config={{ ...config, widget: 'select', 'widget-data-source': { type: 'static', options } } as never}
        />
    );
}
