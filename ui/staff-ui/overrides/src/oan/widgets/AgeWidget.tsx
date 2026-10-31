'use client';

import { useEffect, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { TextInputWidget, setValue, useBaseWidget, type WidgetRootState } from '@openg2p/registry-widgets';
import { formatAge } from './age';

type Config = Record<string, any>;

/*
 * A read-only Age that follows the Date of Birth of the same dialog row while
 * it is typed. The platform has no derived field, so Age stayed blank until
 * the record was saved and the server filled it.
 *
 * Metadata (on the age column):
 *   "widget": "oan-age",
 *   "widget-age-from-date": { "baseField": "date_of_birth" }
 * Outside a dialog the stored value is shown as it is.
 */
export function AgeWidget({ config }: { config: Config }) {
    const dispatch = useDispatch();
    const { widgetId, value } = useBaseWidget({ config: config as never });
    const baseField: string = config['widget-age-from-date']?.baseField || 'date_of_birth';
    const columnKey = String(config['column-key'] || '');
    const inDialog = widgetId.includes('-dlg-') && !!columnKey && widgetId.endsWith(columnKey);
    const baseId = inDialog ? widgetId.slice(0, widgetId.length - columnKey.length) + baseField : null;
    const birth = useSelector((state: WidgetRootState) => (baseId ? state.widget?.values?.[baseId] : undefined));
    const age = useMemo(() => (baseId ? formatAge(birth) : ''), [baseId, birth]);

    useEffect(() => {
        if (!baseId) return;
        const next = age || null;
        if ((value || null) !== next) dispatch(setValue({ widgetId, value: next }));
    }, [age, baseId, dispatch, value, widgetId]);

    return <TextInputWidget config={{ ...config, widget: 'text', 'widget-readonly': true } as never} />;
}
