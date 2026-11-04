'use client';

import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    SelectWidget,
    setDataSource,
    setValues,
    useBaseWidget,
    useWidgetContext,
    type WidgetRootState,
} from '@openg2p/registry-widgets';
import { dialogSiblingId } from './dialog';
import { listValues, matches, type ListValue } from './listValues';

type Config = Record<string, any>;

/*
 * A Master Data dropdown whose options follow another column of the same
 * dialog row. Three optional rules, read from the column's metadata:
 *
 *   "widget-filter-by": { "field": "species", "attribute": "species", "fallback": "unattributed" }
 *       Only the values whose attribute equals that column: the vaccines or the
 *       breeds of the animal's species. With no species yet, or none matching,
 *       the fallback: every value ("all", the default) or only the values that
 *       carry no such attribute ("unattributed": Improved / Local / Hybrid).
 *   "widget-options-by": { "field": "species", "list": "LIVESTOCK_SPECIES", "attribute": "requires_ear_tag",
 *                          "values": { "true": [...], "false": [...] }, "default": [...] }
 *       Only the codes listed for the other column's value, looked up in its own
 *       list: Sex offers Mixed only for a species without an ear tag. Without
 *       "field", or before it is chosen, the "default" codes.
 *   "widget-hide-values": ["EQUINES", "OTHER"]
 *       Values kept in Master Data for older records but not offered for new ones.
 *   "widget-copy-attributes": { "column": "species_rules", "attributes": ["requires_ear_tag", "is_flock_species"] }
 *       Writes the chosen value's attributes into another column of the row as
 *       "requires_ear_tag=true is_flock_species=false", so the platform's show /
 *       require rules ("contains") can follow them: the platform compares one
 *       value per rule and has no "in a list" test.
 *
 * A saved value stays selectable even when the rules leave it out, so an older
 * record still shows what it holds. The list is widget-data-source.params.attribute_id;
 * the stored value is widget-data-source.valueKey (value_id or value_code). The
 * server checks the same rules on save.
 */
export function FilteredSelectWidget({ config }: { config: Config }) {
    const dispatch = useDispatch();
    const { dataSourceRequestHandler } = useWidgetContext();
    // Without its data source: the platform would load the whole list into the
    // store for this field and overwrite the narrowed options.
    const { widgetId, value } = useBaseWidget({ config: { ...config, 'widget-data-source': undefined } as never });
    const source = (config['widget-data-source'] || {}) as Config;
    const listCode: string = source.params?.attribute_id || '';
    const valueKey: 'value_id' | 'value_code' = source.valueKey === 'value_code' ? 'value_code' : 'value_id';
    // Read as strings, so the options are rebuilt only when the metadata itself changes.
    const rulesKey = JSON.stringify([config['widget-filter-by'] || {}, config['widget-options-by'] || null,
        config['widget-hide-values'] || [], config['widget-copy-attributes'] || null]);
    const [filter, optionsBy, hidden, copy] = useMemo(
        () => JSON.parse(rulesKey) as [Config, Config | null, string[], Config | null], [rulesKey]);
    const copyId = copy?.column ? dialogSiblingId(widgetId, config['column-key'], copy.column) : null;
    const filterId = filter.field ? dialogSiblingId(widgetId, config['column-key'], filter.field) : null;
    const optionsById = optionsBy?.field ? dialogSiblingId(widgetId, config['column-key'], optionsBy.field) : null;
    const filterValue = useSelector((state: WidgetRootState) => (filterId ? state.widget?.values?.[filterId] : undefined));
    const optionsByValue = useSelector((state: WidgetRootState) =>
        (optionsById ? state.widget?.values?.[optionsById] : undefined));
    const [rows, setRows] = useState<ListValue[]>([]);
    const [lookup, setLookup] = useState<ListValue[]>([]);
    const lookupList: string = optionsBy?.list || '';

    useEffect(() => {
        let cancelled = false;
        listValues(dataSourceRequestHandler as never, listCode).then((values) => {
            if (!cancelled) setRows(values);
        });
        return () => {
            cancelled = true;
        };
    }, [dataSourceRequestHandler, listCode]);

    useEffect(() => {
        let cancelled = false;
        listValues(dataSourceRequestHandler as never, lookupList).then((values) => {
            if (!cancelled) setLookup(values);
        });
        return () => {
            cancelled = true;
        };
    }, [dataSourceRequestHandler, lookupList]);

    const options = useMemo(() => {
        let shown = rows;
        const attribute: string = filter.attribute || filter.field || '';
        if (filter.field && attribute) {
            const narrowed = filterValue
                ? rows.filter((row) => String(row.attributes?.[attribute] ?? '') === String(filterValue))
                : [];
            const unattributed = rows.filter((row) => !row.attributes?.[attribute]);
            shown = narrowed.length ? narrowed : filter.fallback === 'unattributed' ? unattributed : rows;
        }
        if (optionsBy) {
            const other = optionsByValue ? lookup.find((row) => matches(row, optionsByValue)) : undefined;
            const key = other ? String(other.attributes?.[optionsBy.attribute] ?? '') : '';
            const allowed: unknown = (key && optionsBy.values?.[key]) || optionsBy.default;
            if (Array.isArray(allowed)) shown = shown.filter((row) => allowed.some((code) => matches(row, code)));
        }
        if (hidden.length) shown = shown.filter((row) => !hidden.some((code) => matches(row, code)));
        const list = shown.map((row) => ({ label: row.display || row.value_code, value: row[valueKey] }));
        // A saved value stays selectable even when the rules leave it out.
        if (value && !list.some((o) => o.value === value)) {
            const saved = rows.find((row) => matches(row, value));
            list.unshift({ label: saved?.display || String(value), value: String(value) });
        }
        return list;
    }, [filter, filterValue, hidden, lookup, optionsBy, optionsByValue, rows, value, valueKey]);

    // The platform's select reads its options from the store and loads a static
    // list only once, so the narrowed list is written there whenever it changes.
    useEffect(() => {
        if (rows.length) dispatch(setDataSource({ widgetId, data: options }));
    }, [dispatch, options, rows.length, widgetId]);

    // The chosen value's attributes, copied into the column the show / require rules read.
    const copied = useMemo(() => {
        if (!copy) return null;
        const row = value ? rows.find((r) => matches(r, value)) : undefined;
        const names: string[] = Array.isArray(copy.attributes) ? copy.attributes : [];
        return row ? names.map((name) => `${name}=${String(row.attributes?.[name] ?? '')}`).join(' ') : '';
    }, [copy, rows, value]);
    useEffect(() => {
        if (copyId && copied !== null) dispatch(setValues({ [copyId]: copied }));
    }, [copied, copyId, dispatch]);

    if (!rows.length) {
        // Master Data catalogue not reachable: the platform's own list widget.
        return <SelectWidget config={{ ...config, widget: 'select' } as never} />;
    }
    return (
        <SelectWidget
            config={{ ...config, widget: 'select', 'widget-data-source': { type: 'static', options } } as never}
        />
    );
}

const RULE_KEYS = ['widget-filter-by', 'widget-options-by', 'widget-hide-values', 'widget-copy-attributes'];

/*
 * Registered as "select": a column with one of the rules above is the filtered
 * dropdown, every other select is the platform's own, unchanged. The columns
 * keep "widget": "select" because the dialog table shows a cell's label (not
 * its code) only for that widget name.
 */
export function OanSelectWidget({ config }: { config: Config }) {
    return RULE_KEYS.some((key) => config[key])
        ? <FilteredSelectWidget config={config} />
        : <SelectWidget config={config as never} />;
}
