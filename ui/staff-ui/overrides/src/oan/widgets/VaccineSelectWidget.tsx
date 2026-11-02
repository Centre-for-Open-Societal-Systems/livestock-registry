'use client';

import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    SelectWidget,
    setDataSource,
    useBaseWidget,
    useWidgetContext,
    type WidgetRootState,
} from '@openg2p/registry-widgets';
import { dialogSiblingId } from './dialog';
import { listValues, matches, type ListValue } from './listValues';

type Config = Record<string, any>;

/*
 * A Master Data dropdown narrowed by another column of the same dialog row,
 * through a per-value attribute: on the Vaccination dialog, only the vaccines
 * whose "species" attribute is the animal's species (filled by the ear tag
 * picker). With no species yet, or none matching, every value is offered.
 * The server still checks that the vaccine belongs to the animal's species.
 *
 * Metadata (on the vaccine column, keeping its widget-data-source):
 *   "widget": "oan-vaccine-select",
 *   "widget-filter-by": { "field": "species", "attribute": "species" }
 * The list is widget-data-source.params.attribute_id; the stored value is
 * widget-data-source.valueKey (value_id or value_code).
 */
export function VaccineSelectWidget({ config }: { config: Config }) {
    const dispatch = useDispatch();
    const { dataSourceRequestHandler } = useWidgetContext();
    // Without its data source: the platform would load the whole list into the
    // store for this field and overwrite the narrowed options.
    const { widgetId, value } = useBaseWidget({ config: { ...config, 'widget-data-source': undefined } as never });
    const source = (config['widget-data-source'] || {}) as Config;
    const listCode: string = source.params?.attribute_id || '';
    const valueKey: 'value_id' | 'value_code' = source.valueKey === 'value_code' ? 'value_code' : 'value_id';
    const filter = (config['widget-filter-by'] || {}) as Config;
    const fieldId = filter.field ? dialogSiblingId(widgetId, config['column-key'], filter.field) : null;
    const filterValue = useSelector((state: WidgetRootState) => (fieldId ? state.widget?.values?.[fieldId] : undefined));
    const [rows, setRows] = useState<ListValue[]>([]);

    useEffect(() => {
        let cancelled = false;
        listValues(dataSourceRequestHandler as never, listCode).then((values) => {
            if (!cancelled) setRows(values);
        });
        return () => {
            cancelled = true;
        };
    }, [dataSourceRequestHandler, listCode]);

    const options = useMemo(() => {
        const attribute: string = filter.attribute || filter.field || '';
        const narrowed = filterValue && attribute
            ? rows.filter((row) => String(row.attributes?.[attribute] ?? '') === String(filterValue))
            : [];
        const shown = narrowed.length ? narrowed : rows;
        const list = shown.map((row) => ({ label: row.display || row.value_code, value: row[valueKey] }));
        // A saved vaccine stays selectable even when it no longer matches the species.
        if (value && !list.some((o) => o.value === value)) {
            const saved = rows.find((row) => matches(row, value));
            list.unshift({ label: saved?.display || String(value), value: String(value) });
        }
        return list;
    }, [filter.attribute, filter.field, filterValue, rows, value, valueKey]);

    // The platform's select reads its options from the store and loads a static
    // list only once, so the narrowed list is written there whenever it changes.
    useEffect(() => {
        if (rows.length) dispatch(setDataSource({ widgetId, data: options }));
    }, [dispatch, options, rows.length, widgetId]);

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
