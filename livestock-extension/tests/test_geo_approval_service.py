"""Server-generated context keeps proposed addresses out of update routing."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip('openg2p_registry_core')

from openg2p_registry_livestock_extension.geo_approval import service


@pytest.mark.parametrize('approved', [{'woreda': 'old-woreda'}, {}])
def test_existing_record_uses_approved_scope_even_when_proposal_supplies_a_scope(approved):
    instance = service.GeoAweIntegrationService()
    request = SimpleNamespace(register_id='registry', internal_record_id='row', section_id='section')
    configured = SimpleNamespace(context_field_names=['geo_woreda_id', 'geo_woreda_approver_ids'])
    native = AsyncMock()
    generated = {'geo_woreda_id': 'old-woreda', 'geo_woreda_approver_ids': ['scoped-reviewer']}
    context = AsyncMock(return_value=generated)
    proposed = [{'woreda': 'proposed-woreda', 'geo_woreda_approver_ids': ['injected-user']}]
    with patch.object(instance, '_awe_enabled', return_value=True), \
         patch.object(service.G2PAwePolicyConfigurationService, 'get_component',
                      return_value=SimpleNamespace(find_effective_policy_configuration=AsyncMock(return_value=configured))), \
         patch.object(service, '_approved_record', AsyncMock(return_value=approved)), \
         patch.object(instance, '_geo_context', context), \
         patch.object(service.G2PAweIntegrationService, 'start_change_request_workflow', native):
        asyncio.run(instance.start_change_request_workflow(None, request, proposed, bearer_token='test-token', requester='requester'))
    assert context.call_args.args[3:] == (approved,)
    assert native.call_args.args[2][-1] == generated
    assert proposed[0]['woreda'] == 'proposed-woreda'
