"""Functional-ID affixes per register.

The platform allocates the numeric part; this only decides what it is wrapped in.
The Farmer prefix stays `FR-` because that is the format the Farmer Registry issues
and that `_check_farmer_id_format` in g2p_livestock_registry validates against
(`FR-` followed by ten digits).

Note the OAN ID on a livestock holding is a different identifier: it is built from the
farmer code and first name (e.g. FR-1234567890-ABEBE-001) by the Odoo module's
`_generate_oan_id`, and is carried on the record as `oan_id` rather than allocated
here.
"""

from openg2p_fastapi_common.service import BaseService
from openg2p_registry_core.interfaces import G2PIdGeneratorInterface, IdAffix
from openg2p_registry_core.models.g2p_register import G2PRegister


class G2PIdGeneratorService(BaseService, G2PIdGeneratorInterface):

    def generate_prefix_suffix(
        self, g2p_register: G2PRegister, register_mnemonic: str
    ) -> IdAffix:
        mnemonic = (register_mnemonic or "").lower()

        if mnemonic == "farmer":
            return IdAffix(prefix="FR-", suffix="")
        if mnemonic == "livestock":
            return IdAffix(prefix="LS-", suffix="")
        if mnemonic == "animal":
            return IdAffix(prefix="AN-", suffix="")
        if mnemonic == "healthevent":
            return IdAffix(prefix="HE-", suffix="")
        if mnemonic == "vaccination":
            return IdAffix(prefix="VC-", suffix="")
        if mnemonic == "vitalevent":
            return IdAffix(prefix="VE-", suffix="")
        if mnemonic == "breeding":
            return IdAffix(prefix="BR-", suffix="")
        if mnemonic == "vaccineschedule":
            return IdAffix(prefix="VS-", suffix="")
        if mnemonic == "importbatch":
            return IdAffix(prefix="IB-", suffix="")
        if mnemonic == "auditlog":
            return IdAffix(prefix="AL-", suffix="")

        return IdAffix(prefix="DEFAULT-", suffix="")
