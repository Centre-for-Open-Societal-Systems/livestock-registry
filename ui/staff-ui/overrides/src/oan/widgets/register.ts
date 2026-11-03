import { createElement } from 'react';
import { DateInputWidget, widgetRegistry } from '@openg2p/registry-widgets';
import { AgeWidget } from './AgeWidget';
import { AnimalPickerWidget } from './AnimalPickerWidget';
import { GeoPointWidget } from './GeoPointWidget';
import { NextDueDateWidget } from './NextDueDateWidget';
import { VaccineSelectWidget } from './VaccineSelectWidget';
import {
    ETHIOPIAN_DATE_CELL,
    ETHIOPIAN_DATE_VARIANT,
    EthiopianDateInputWidget,
} from './EthiopianDateInputWidget';

type Props = { config: Record<string, unknown> } & Record<string, unknown>;

function DateOrVariant(props: Props) {
    if (props.config['widget-variant'] === ETHIOPIAN_DATE_VARIANT) {
        return createElement(EthiopianDateInputWidget, props as never);
    }
    return createElement(DateInputWidget, props as never);
}

// Preserve the native date widget unless metadata explicitly asks for the
// Ethiopian entry variant. Table date cells need a custom widget type because
// the upstream TableCellDate does not inspect widget variants.
widgetRegistry.register({ widget: 'date', component: DateOrVariant });
widgetRegistry.register({ widget: ETHIOPIAN_DATE_CELL, component: EthiopianDateInputWidget as never });

// Native defaults remain registered; add the domain widgets.
widgetRegistry.register({ widget: 'oan-geo-point', component: GeoPointWidget as never });
// Event dialogs: the ear tag picked from this form's (or record's) animals, filling Species and Age.
widgetRegistry.register({ widget: 'oan-animal-picker', component: AnimalPickerWidget as never });
// Livestock Details dialog: Age follows the Date of Birth as it is typed.
widgetRegistry.register({ widget: 'oan-age', component: AgeWidget as never });
// Vaccination dialog: only the vaccines of the animal's species.
widgetRegistry.register({ widget: 'oan-vaccine-select', component: VaccineSelectWidget as never });
// Vaccination dialog: Next Due Date from the vaccination date and the vaccine's interval.
widgetRegistry.register({ widget: 'oan-next-due-date', component: NextDueDateWidget as never });
