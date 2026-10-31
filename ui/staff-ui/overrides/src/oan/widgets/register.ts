import { widgetRegistry } from '@openg2p/registry-widgets';
import { AgeWidget } from './AgeWidget';
import { AnimalPickerWidget } from './AnimalPickerWidget';
import { GeoPointWidget } from './GeoPointWidget';

// Native defaults remain registered; add only the domain widgets.
widgetRegistry.register({ widget: 'oan-geo-point', component: GeoPointWidget as never });
// Event dialogs: the ear tag picked from this form's animals, filling Species and Age.
widgetRegistry.register({ widget: 'oan-animal-picker', component: AnimalPickerWidget as never });
// Livestock Details dialog: Age follows the Date of Birth as it is typed.
widgetRegistry.register({ widget: 'oan-age', component: AgeWidget as never });
