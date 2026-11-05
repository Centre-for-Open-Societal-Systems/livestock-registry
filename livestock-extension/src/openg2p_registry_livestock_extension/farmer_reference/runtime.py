"""Idempotent component registration using the upstream Farmer pattern."""
from openg2p_fastapi_common.context import component_registry
from .native import (G2PIntakeFormDataService, G2PRegisterChangeRequestService,
                     G2PChangeRequestWorkerService, G2PAweWebhookService,
                     ReferenceIntakeService, ReferenceChangeRequestService,
                     ReferenceIngestionService, ReferenceWebhookService)


def install():
    for extension, base in ((ReferenceIntakeService, G2PIntakeFormDataService),
                            (ReferenceChangeRequestService, G2PRegisterChangeRequestService),
                            (ReferenceIngestionService, G2PChangeRequestWorkerService),
                            (ReferenceWebhookService, G2PAweWebhookService)):
        instance = next((item for item in component_registry if isinstance(item, extension)), None) or extension()
        if instance in component_registry:
            component_registry.remove(instance)
        first = next((index for index, item in enumerate(component_registry) if isinstance(item, base)), len(component_registry))
        component_registry.insert(first, instance)
