# ruff: noqa: E402
import asyncio
import logging

from .config import Settings

_config = Settings.get_config()

from openg2p_fastapi_common.app import Initializer as BaseInitializer
from openg2p_registry_core.app import Initializer as CoreInitializer

from .register_domain.models import (
    G2PRegisterFarmer, G2PRegisterHistoryFarmer,
    G2PRegisterLivestock, G2PRegisterHistoryLivestock,
    G2PRegisterAnimal, G2PRegisterHistoryAnimal,
    G2PRegisterHealthEvent, G2PRegisterHistoryHealthEvent,
    G2PRegisterVaccination, G2PRegisterHistoryVaccination,
    G2PRegisterVitalEvent, G2PRegisterHistoryVitalEvent,
    G2PRegisterBreeding, G2PRegisterHistoryBreeding,
    G2PRegisterVaccineSchedule, G2PRegisterHistoryVaccineSchedule,
    G2PRegisterImportBatch, G2PRegisterHistoryImportBatch,
    G2PRegisterAuditLog, G2PRegisterHistoryAuditLog,
    G2PIntakeFormFarmer, G2PIntakeFormLivestock, G2PIntakeFormAnimal,
    G2PIntakeFormHealthEvent, G2PIntakeFormVaccination, G2PIntakeFormVitalEvent,
    G2PIntakeFormBreeding, G2PIntakeFormVaccineSchedule, G2PIntakeFormImportBatch,
    G2PIntakeFormAuditLog,
)
from .register_domain.factory import G2PRegisterDomainFactory
from .register_domain.services import (
    G2PRegisterDomainServiceFarmer, G2PRegisterDomainServiceLivestock,
    G2PRegisterDomainServiceAnimal, G2PRegisterDomainServiceHealthEvent,
    G2PRegisterDomainServiceVaccination, G2PRegisterDomainServiceVitalEvent,
    G2PRegisterDomainServiceBreeding, G2PRegisterDomainServiceVaccineSchedule,
    G2PRegisterDomainServiceImportBatch, G2PRegisterDomainServiceAuditLog,
)

_logger = logging.getLogger(_config.logging_default_logger_name)


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().initialize()
        CoreInitializer().initialize()

        G2PRegisterDomainFactory()
        G2PRegisterDomainServiceFarmer()
        G2PRegisterDomainServiceLivestock()
        G2PRegisterDomainServiceAnimal()
        G2PRegisterDomainServiceHealthEvent()
        G2PRegisterDomainServiceVaccination()
        G2PRegisterDomainServiceVitalEvent()
        G2PRegisterDomainServiceBreeding()
        G2PRegisterDomainServiceVaccineSchedule()
        G2PRegisterDomainServiceImportBatch()
        G2PRegisterDomainServiceAuditLog()

    def migrate_database(self, args):

        async def migrate():
            _logger.info("Migrating extensions database")

            # Farmer first: the livestock record carries the farmer's identifiers.
            await G2PRegisterFarmer.create_migrate()
            await G2PRegisterHistoryFarmer.create_migrate()
            await G2PIntakeFormFarmer.create_migrate()

            await G2PRegisterLivestock.create_migrate()
            await G2PRegisterHistoryLivestock.create_migrate()
            await G2PIntakeFormLivestock.create_migrate()

            # The animals and the event lines, all children of the livestock record.
            await G2PRegisterAnimal.create_migrate()
            await G2PRegisterHistoryAnimal.create_migrate()
            await G2PIntakeFormAnimal.create_migrate()

            await G2PRegisterHealthEvent.create_migrate()
            await G2PRegisterHistoryHealthEvent.create_migrate()
            await G2PIntakeFormHealthEvent.create_migrate()

            await G2PRegisterVaccination.create_migrate()
            await G2PRegisterHistoryVaccination.create_migrate()
            await G2PIntakeFormVaccination.create_migrate()

            await G2PRegisterVitalEvent.create_migrate()
            await G2PRegisterHistoryVitalEvent.create_migrate()
            await G2PIntakeFormVitalEvent.create_migrate()

            await G2PRegisterBreeding.create_migrate()
            await G2PRegisterHistoryBreeding.create_migrate()
            await G2PIntakeFormBreeding.create_migrate()

            await G2PRegisterVaccineSchedule.create_migrate()
            await G2PRegisterHistoryVaccineSchedule.create_migrate()
            await G2PIntakeFormVaccineSchedule.create_migrate()

            await G2PRegisterImportBatch.create_migrate()
            await G2PRegisterHistoryImportBatch.create_migrate()
            await G2PIntakeFormImportBatch.create_migrate()

            await G2PRegisterAuditLog.create_migrate()
            await G2PRegisterHistoryAuditLog.create_migrate()
            await G2PIntakeFormAuditLog.create_migrate()

        asyncio.run(migrate())
