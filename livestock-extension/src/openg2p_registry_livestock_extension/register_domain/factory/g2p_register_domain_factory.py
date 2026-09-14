import importlib
import logging
from typing import Optional

from openg2p_fastapi_common.service import BaseService
from openg2p_registry_core.services import G2PRegisterDomainService

_logger = logging.getLogger('g2p-register-domain-factory')

class G2PRegisterDomainFactory(BaseService):

    g2p_register_domain_service: G2PRegisterDomainService = None

    def get_domain_service(self, register_mnemonic: str) -> Optional[G2PRegisterDomainService]:

        try:
            # Import via the extension-agnostic alias (see
            # openg2p_registry_staff_api/main.py's "Option C" sys.modules
            # aliasing, and openg2p_registry_core/services/intake_form_data_service.py's
            # _DOMAIN_MODELS_MODULE), NOT this extension's own real package
            # name. Startup only ever imports register_domain/services (and
            # everything it pulls in, including every domain model) under
            # that alias -- importing the real name here as a SEPARATE,
            # never-before-used dotted path forces Python to re-execute
            # every domain model module's class body from scratch, which
            # crashes on the second SQLAlchemy declarative class it
            # redefines (sqlalchemy.exc.InvalidRequestError: "Table ... is
            # already defined for this MetaData instance") -- not caught by
            # the except clause below, so it broke saving any intake-form
            # section that reaches a domain service at all.
            module = importlib.import_module("openg2p_registry_extensions.register_domain.services")
            register_class_prefix: str = "G2PRegisterDomainService"
            implementation_class_name: str = f"{register_class_prefix}{register_mnemonic}"
            implementation_class = getattr(module, implementation_class_name)
            _logger.info(f"Found specific implementation for register mnemonic '{register_mnemonic}': {implementation_class_name}")
            g2p_register_domain_service: G2PRegisterDomainService = implementation_class.get_component()
            if not g2p_register_domain_service:
                g2p_register_domain_service = implementation_class()
            return g2p_register_domain_service
        except (AttributeError, ModuleNotFoundError) as error:
            _logger.warning(f"Could not find specific implementation for register mnemonic '{register_mnemonic}': {error}. Falling back to default implementations.")
            return None
