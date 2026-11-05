import { widgetRegistry } from '@openg2p/registry-widgets';
import { AgeWidget } from './AgeWidget';
import { AnimalPickerWidget } from './AnimalPickerWidget';
import { FilteredSelectWidget, OanSelectWidget } from './FilteredSelectWidget';
import { GeoPointWidget } from './GeoPointWidget';
import { NextDueDateWidget } from './NextDueDateWidget';

// Native defaults remain registered; add only the domain widgets.
widgetRegistry.register({ widget: 'oan-geo-point', component: GeoPointWidget as never });
// Event dialogs: the ear tag picked from this form's (or record's) animals, filling Species and Age.
widgetRegistry.register({ widget: 'oan-animal-picker', component: AnimalPickerWidget as never });
// Livestock Details dialog: Age follows the Date of Birth as it is typed.
widgetRegistry.register({ widget: 'oan-age', component: AgeWidget as never });
// A dropdown that follows another column: the vaccines or breeds of the animal's species,
// Sex by the species' ear tag setting. Under "select" it takes over only the columns that
// carry its rules, so their table cells keep showing labels; the other names are kept for
// metadata that still uses them.
widgetRegistry.register({ widget: 'select', component: OanSelectWidget as never });
widgetRegistry.register({ widget: 'oan-filtered-select', component: FilteredSelectWidget as never });
widgetRegistry.register({ widget: 'oan-vaccine-select', component: FilteredSelectWidget as never });
// Vaccination dialog: Next Due Date from the vaccination date and the vaccine's interval.
widgetRegistry.register({ widget: 'oan-next-due-date', component: NextDueDateWidget as never });
