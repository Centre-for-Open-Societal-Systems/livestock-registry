'use client';

import { useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { DateInputWidget, setValue, useBaseWidget, useWidgetContext, type WidgetRootState } from '@openg2p/registry-widgets';
import { dialogSiblingId } from './dialog';
import { listValues, matches, type ListValue } from './listValues';

type Config = Record<string, any>;

/*
 * Next Due Date on the Vaccination dialog: the vaccination date plus the
 * chosen vaccine's interval (Master Data VACCINE_TYPE attribute
 * interval_days), shown as soon as both are picked. The server fills the same
 * date on save when it is left empty; a date the user typed is never
 * replaced, and a vaccine without an interval leaves it empty.
 *
 * Metadata (on the next due date column):
 *   "widget": "oan-next-due-date",
 *   "widget-date-offset": { "baseField": "vaccination_date", "optionsField": "vaccine_type",
 *                           "daysKey": "interval_days", "listCode": "VACCINE_TYPE" }
 */

const parse = (text: unknown): { date: Date; iso: boolean } | null => {
    const value = String(text ?? '').trim();
    let m = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return { date: new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])), iso: true };
    m = value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m) return { date: new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1])), iso: false };
    return null;
};

const pad = (n: number) => String(n).padStart(2, '0');

// The due date in the same text form as the vaccination date it comes from.
export function addDays(base: unknown, days: number): string | null {
    const parsed = parse(base);
    if (!parsed || !Number.isFinite(days) || days < 1) return null;
    const d = new Date(parsed.date.getFullYear(), parsed.date.getMonth(), parsed.date.getDate() + days);
    return parsed.iso
        ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
        : `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

export function NextDueDateWidget({ config }: { config: Config }) {
    const dispatch = useDispatch();
    const { dataSourceRequestHandler } = useWidgetContext();
    const { widgetId, value } = useBaseWidget({ config: config as never });
    const offset = (config['widget-date-offset'] || {}) as Config;
    const baseId = dialogSiblingId(widgetId, config['column-key'], offset.baseField || 'vaccination_date');
    const optionId = dialogSiblingId(widgetId, config['column-key'], offset.optionsField || 'vaccine_type');
    const base = useSelector((state: WidgetRootState) => (baseId ? state.widget?.values?.[baseId] : undefined));
    const option = useSelector((state: WidgetRootState) => (optionId ? state.widget?.values?.[optionId] : undefined));
    const [rows, setRows] = useState<ListValue[]>([]);
    const lastFilled = useRef<string | null>(null);

    useEffect(() => {
        if (!baseId) return;
        let cancelled = false;
        listValues(dataSourceRequestHandler as never, offset.listCode || 'VACCINE_TYPE').then((values) => {
            if (!cancelled) setRows(values);
        });
        return () => {
            cancelled = true;
        };
    }, [baseId, dataSourceRequestHandler, offset.listCode]);

    useEffect(() => {
        if (!baseId) return;
        // Only an empty date, or the one this widget filled, follows the inputs.
        const current = value ? String(value) : null;
        if (current && current !== lastFilled.current) return;
        const row = rows.find((r) => matches(r, option));
        const days = Number(row?.attributes?.[offset.daysKey || 'interval_days']);
        const next = row ? addDays(base, days) : null;
        if (next === current) return;
        lastFilled.current = next;
        dispatch(setValue({ widgetId, value: next }));
    }, [base, baseId, dispatch, offset.daysKey, option, rows, value, widgetId]);

    return <DateInputWidget config={{ ...config, widget: 'date' } as never} />;
}
