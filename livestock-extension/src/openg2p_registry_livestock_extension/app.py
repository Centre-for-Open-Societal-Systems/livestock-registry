# ruff: noqa: E402
"""Domain initialization using the upstream Farmer 1.2 extension pattern."""
import asyncio
from .config import Settings
_config = Settings.get_config()
from openg2p_fastapi_common.app import Initializer as BaseInitializer
from openg2p_registry_core.app import Initializer as CoreInitializer
from .register_domain import models, services

MODEL_NAMES = ['G2PRegisterFarmer', 'G2PRegisterHistoryFarmer', 'G2PIntakeFormFarmer', 'G2PRegisterLivestock', 'G2PRegisterHistoryLivestock', 'G2PIntakeFormLivestock', 'G2PRegisterAnimal', 'G2PRegisterHistoryAnimal', 'G2PIntakeFormAnimal', 'G2PRegisterHealthEvent', 'G2PRegisterHistoryHealthEvent', 'G2PIntakeFormHealthEvent', 'G2PRegisterVaccination', 'G2PRegisterHistoryVaccination', 'G2PIntakeFormVaccination', 'G2PRegisterVitalEvent', 'G2PRegisterHistoryVitalEvent', 'G2PIntakeFormVitalEvent', 'G2PRegisterBreeding', 'G2PRegisterHistoryBreeding', 'G2PIntakeFormBreeding', 'G2PRegisterRetagging', 'G2PRegisterHistoryRetagging', 'G2PIntakeFormRetagging', 'G2PRegisterVaccineSchedule', 'G2PRegisterHistoryVaccineSchedule', 'G2PIntakeFormVaccineSchedule', 'G2PRegisterImportBatch', 'G2PRegisterHistoryImportBatch', 'G2PIntakeFormImportBatch', 'G2PRegisterAuditLog', 'G2PRegisterHistoryAuditLog', 'G2PIntakeFormAuditLog', 'G2PLivestockSpeciesConfig']
SERVICE_NAMES = ['G2PRegisterDomainServiceAnimal', 'G2PRegisterDomainServiceAuditLog', 'G2PRegisterDomainServiceBreeding', 'G2PRegisterDomainServiceFarmer', 'G2PRegisterDomainServiceHealthEvent', 'G2PRegisterDomainServiceImportBatch', 'G2PRegisterDomainServiceLivestock', 'G2PRegisterDomainServiceRetagging', 'G2PRegisterDomainServiceVaccination', 'G2PRegisterDomainServiceVaccineSchedule', 'G2PRegisterDomainServiceVitalEvent']


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().initialize()
        CoreInitializer().initialize()
        for name in SERVICE_NAMES:
            getattr(services, name)()

    def migrate_database(self, args):
        async def migrate():
            # Native create_migrate only. Existing-table changes remain gated
            # on an explicit migration and restored-copy preservation evidence.
            for name in MODEL_NAMES:
                await getattr(models, name).create_migrate()
        asyncio.run(migrate())
