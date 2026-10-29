"""Functional-ID affixes per register.

The platform allocates the numeric part; this only decides what it is wrapped in.
The Farmer register keeps the `FR-` prefix. Its internally generated functional
ID is separate from the externally supplied `farmer_id`, which the domain
services validate as `FR-` followed by twelve digits.

Note the OAN ID on a livestock holding is a different identifier: it is built from the
farmer code and first name (e.g. FR-123456789012-ABEBE-001) by the Odoo module's
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
        if mnemonic == "retagging":
            return IdAffix(prefix="RT-", suffix="")
        if mnemonic == "vaccineschedule":
            return IdAffix(prefix="VS-", suffix="")
        if mnemonic == "auditlog":
            return IdAffix(prefix="AL-", suffix="")

        return IdAffix(prefix="DEFAULT-", suffix="")
