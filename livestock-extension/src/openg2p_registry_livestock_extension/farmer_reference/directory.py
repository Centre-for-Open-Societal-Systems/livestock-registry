"""Read-only standard role/policy intersection; no identity writes or attributes.

Supported geographic assignments are finite Woreda-ID EQ/IN policy trees on
the Farmer register. Broader/unknown filters block routing for that candidate;
they are never interpreted as permission for every location.
"""
from urllib.parse import quote
from sqlalchemy import select
from openg2p_registry_core.helpers.data_policy_keycloak_helper import DataPolicyKeycloakHelper
from openg2p_registry_core.models import G2PRegistryDataPolicy

from .geography import ApproverEligibility, FARMER_APPROVER_ROLE, policy_woredas
from .profile import FarmerReferenceError


class PolicyDirectory:
    async def candidates(self, session, farmer_register_id):
        helper = DataPolicyKeycloakHelper()
        # Reading existing assignments does not require enabling publication.
        cfg = helper._config
        if not all((cfg.keycloak_admin_url, cfg.keycloak_admin_client_id,
                    cfg.keycloak_admin_client_secret, cfg.keycloak_client_id, cfg.keycloak_realm)):
            raise FarmerReferenceError("FARMER_REFERENCE_IAM_DIRECTORY_REQUIRED")
        realm = quote(helper._config.keycloak_realm, safe="")
        client_id = await helper._resolve_client_uuid(helper._registry_client_id())
        base = f"/realms/{realm}"
        users = []
        for start in range(0, 10001, 100):
            page = await helper._admin_request("GET",
                f"{base}/clients/{quote(client_id, safe='')}/roles/{quote(FARMER_APPROVER_ROLE, safe='')}/users",
                params={"first": start, "max": 100})
            if not isinstance(page, list):
                raise FarmerReferenceError("FARMER_REFERENCE_IAM_DIRECTORY_INVALID")
            users.extend(page)
            if len(page) < 100:
                break
        else:
            raise FarmerReferenceError("FARMER_REFERENCE_IAM_DIRECTORY_LIMIT")
        policies = (await session.execute(select(G2PRegistryDataPolicy).where(
            G2PRegistryDataPolicy.register_id == farmer_register_id,
            G2PRegistryDataPolicy.policy_target == "REGISTER_RECORD"))).scalars().all()
        result = []
        for user in users:
            if not user.get("enabled", False) or not user.get("id"):
                continue
            roles = await helper._admin_request("GET",
                f"{base}/users/{quote(user['id'], safe='')}/role-mappings/clients/{quote(client_id, safe='')}/composite")
            if not isinstance(roles, list):
                raise FarmerReferenceError("FARMER_REFERENCE_IAM_DIRECTORY_INVALID")
            names = {role.get("name") for role in roles if isinstance(role, dict)}
            if FARMER_APPROVER_ROLE not in names:
                continue
            assigned = [policy for policy in policies if "DP_" + policy.policy_mnemonic in names]
            scopes = policy_woredas(assigned)
            # Matches AWE's native Keycloak assignee ordering.
            user_id = user.get("preferred_username") or user.get("username") or user["id"]
            result.append(ApproverEligibility(user_id, frozenset({FARMER_APPROVER_ROLE}), scopes))
        return tuple(result)
