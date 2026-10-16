# ruff: noqa: E402
import asyncio
import logging

from .config import Settings

_config = Settings.get_config()

from openg2p_fastapi_common.app import Initializer as BaseInitializer
from openg2p_fastapi_common.context import dbengine
from openg2p_registry_core.app import Initializer as CoreInitializer

# Per-species configuration (ear tag required / flock species) is a table this
# extension owns: the platform keeps no code lists since registry-platform 1.2
# (they are read from Master Data), so there is no attribute row to hang it on.
from .register_domain.models.species_config import G2PLivestockSpeciesConfig
from .schema_sync import add_missing_columns

from .register_domain.models import (
    G2PRegisterFarmer, G2PRegisterHistoryFarmer,
    G2PRegisterLivestock, G2PRegisterHistoryLivestock,
    G2PRegisterAnimal, G2PRegisterHistoryAnimal,
    G2PRegisterHealthEvent, G2PRegisterHistoryHealthEvent,
    G2PRegisterVaccination, G2PRegisterHistoryVaccination,
    G2PRegisterVitalEvent, G2PRegisterHistoryVitalEvent,
    G2PRegisterBreeding, G2PRegisterHistoryBreeding,
    G2PRegisterRetagging, G2PRegisterHistoryRetagging,
    G2PRegisterVaccineSchedule, G2PRegisterHistoryVaccineSchedule,
    G2PRegisterImportBatch, G2PRegisterHistoryImportBatch,
    G2PRegisterAuditLog, G2PRegisterHistoryAuditLog,
    G2PIntakeFormFarmer, G2PIntakeFormLivestock, G2PIntakeFormAnimal,
    G2PIntakeFormHealthEvent, G2PIntakeFormVaccination, G2PIntakeFormVitalEvent,
    G2PIntakeFormBreeding, G2PIntakeFormVaccineSchedule, G2PIntakeFormImportBatch,
    G2PIntakeFormAuditLog, G2PIntakeFormRetagging,
)
from .register_domain.factory import G2PRegisterDomainFactory
from .register_domain.services import (
    G2PRegisterDomainServiceFarmer, G2PRegisterDomainServiceLivestock,
    G2PRegisterDomainServiceAnimal, G2PRegisterDomainServiceHealthEvent,
    G2PRegisterDomainServiceVaccination, G2PRegisterDomainServiceVitalEvent,
    G2PRegisterDomainServiceBreeding, G2PRegisterDomainServiceVaccineSchedule,
    G2PRegisterDomainServiceImportBatch, G2PRegisterDomainServiceAuditLog,
    G2PRegisterDomainServiceRetagging,
)
from .register_domain.controllers import (
    G2PAnimalBulkImportController,
    G2PApproverResolverController,
    G2PLivestockFormConfigController,
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
        G2PRegisterDomainServiceRetagging()
        G2PRegisterDomainServiceVaccineSchedule()
        G2PRegisterDomainServiceImportBatch()
        G2PRegisterDomainServiceAuditLog()

        # Custom HTTP endpoint (not a domain service hook) — see
        # register_domain/controllers/g2p_animal_bulk_import_controller.py.
        # post_init() registers the router onto the shared FastAPI app the
        # same way every platform controller does
        # (openg2p_fastapi_common.controller.BaseController.post_init).
        G2PAnimalBulkImportController().post_init()
        # Server-to-server endpoint AWE's "http" approver-rule calls to
        # resolve who approves each stage of the hierarchical Kebele ->
        # Woreda -> Zone -> Region chain, scoped to the record's own
        # location — see g2p_approver_resolver_controller.py.
        G2PApproverResolverController().post_init()
        # Per-value configuration the dialog overlay reads (species config,
        # vaccine intervals): on registry-platform 1.2 the code lists come
        # from Master Data and carry nothing livestock-specific — see
        # g2p_form_config_controller.py.
        G2PLivestockFormConfigController().post_init()

    def migrate_database(self, args):

        async def migrate():
            _logger.info("Migrating extensions database")

            # The core migration ran in its own asyncio.run() just before this
            # one, and the shared engine's pool still holds connections bound to
            # that closed event loop. Reusing one fails the first query here with
            # "got Future ... attached to a different loop", and every livestock
            # table goes missing. Dispose of the pool so this loop opens its own.
            if dbengine.get() is not None:
                await dbengine.get().dispose()

            # The species-config table stands alone (nothing references it), so
            # it comes first. Without it the animal rules answer 500 on the
            # first save: the model is in the image, only the table is missing.
            await G2PLivestockSpeciesConfig.create_migrate()

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

            await G2PRegisterRetagging.create_migrate()
            await G2PRegisterHistoryRetagging.create_migrate()
            await G2PIntakeFormRetagging.create_migrate()

            await G2PRegisterVaccineSchedule.create_migrate()
            await G2PRegisterHistoryVaccineSchedule.create_migrate()
            await G2PIntakeFormVaccineSchedule.create_migrate()

            await G2PRegisterImportBatch.create_migrate()
            await G2PRegisterHistoryImportBatch.create_migrate()
            await G2PIntakeFormImportBatch.create_migrate()

            await G2PRegisterAuditLog.create_migrate()
            await G2PRegisterHistoryAuditLog.create_migrate()
            await G2PIntakeFormAuditLog.create_migrate()

            # create_migrate() never adds a column to a table that already
            # exists, so a database first created on an older platform lacks
            # the columns added since (e.g. subject_internal_record_id on the
            # history tables, which 1.2 writes on every register ingest).
            await add_missing_columns(dbengine.get(), [
                G2PLivestockSpeciesConfig,
                G2PRegisterFarmer, G2PRegisterHistoryFarmer, G2PIntakeFormFarmer,
                G2PRegisterLivestock, G2PRegisterHistoryLivestock, G2PIntakeFormLivestock,
                G2PRegisterAnimal, G2PRegisterHistoryAnimal, G2PIntakeFormAnimal,
                G2PRegisterHealthEvent, G2PRegisterHistoryHealthEvent, G2PIntakeFormHealthEvent,
                G2PRegisterVaccination, G2PRegisterHistoryVaccination, G2PIntakeFormVaccination,
                G2PRegisterVitalEvent, G2PRegisterHistoryVitalEvent, G2PIntakeFormVitalEvent,
                G2PRegisterBreeding, G2PRegisterHistoryBreeding, G2PIntakeFormBreeding,
                G2PRegisterRetagging, G2PRegisterHistoryRetagging, G2PIntakeFormRetagging,
                G2PRegisterVaccineSchedule, G2PRegisterHistoryVaccineSchedule, G2PIntakeFormVaccineSchedule,
                G2PRegisterImportBatch, G2PRegisterHistoryImportBatch, G2PIntakeFormImportBatch,
                G2PRegisterAuditLog, G2PRegisterHistoryAuditLog, G2PIntakeFormAuditLog,
            ])

        asyncio.run(migrate())
