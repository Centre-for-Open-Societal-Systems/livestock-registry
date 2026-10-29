#!/usr/bin/env bash
set -euo pipefail
case "${1:-source}" in source|--native) ;; *) echo "Usage: ci/validate.sh [--native]" >&2; exit 2 ;; esac
export REGISTRY_EXTENSION_MODULE=openg2p_registry_livestock_extension
export PYTHONPATH="livestock-extension/src${PYTHONPATH:+:$PYTHONPATH}"
python -m ruff check --no-cache --select E9,F63,F7,F82 livestock-extension/src livestock-extension/tests
python -m pytest -q -p no:cacheprovider test/test_sample_loader.py test/test_rp_pin_lockstep.py test/test_oan_chart.py test/test_deployment_guard.py test/test_onboarding_runner_failure.py test/test_metadata_transitions.py test/test_default_approvals.py test/test_verified_update_policy.py
# Native suites require the published OpenG2P runtime. GitHub's native-image
# step runs these independently; Jenkins requests this mode inside that image.
if [[ "${1:-source}" == --native ]]; then
  python -c 'import openg2p_registry_core'
  python -m pytest -q -p no:cacheprovider livestock-extension/tests
fi
python ci/refactor/check_port.py . livestock
find ci ui/staff-ui/scripts -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
