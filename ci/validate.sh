#!/usr/bin/env bash
set -euo pipefail
case "${1:-source}" in source|--native) ;; *) echo "Usage: ci/validate.sh [--native]" >&2; exit 2 ;; esac
export REGISTRY_EXTENSION_MODULE=openg2p_registry_livestock_extension
export PYTHONPATH="livestock-extension/src${PYTHONPATH:+:$PYTHONPATH}"
# The rules are in ruff.toml.
python -m ruff check --no-cache .
# Coverage of livestock-extension/src is reported, not enforced: no minimum until one is agreed (ci/README.md).
# Jenkins mounts the repository read-only, so the data file goes to the temporary directory.
export COVERAGE_FILE="${TMPDIR:-/tmp}/livestock-registry.coverage"
COVERAGE=(--cov=livestock-extension/src --cov-report=term:skip-covered)
# Every test in test/, so a new test file runs without being listed here. test/sanity runs against a deployment.
python -m pytest -q -p no:cacheprovider test --ignore=test/sanity ci/connector/tests "${COVERAGE[@]}"
# The ODK transform against the sample submissions (natural and AI breeding).
python odk/test_transform.py
# The Node tests: the staff UI widgets (they import TypeScript, which Node runs from 22.18) and the staging dashboard
# access proxy. The Jenkins test image has no Node; the GitHub contracts check runs them, and Jenkins deploys only
# when every GitHub check is green.
if command -v node > /dev/null; then
  node --test test/*.test.mjs scripts/operations/staging-dashboard/access-proxy.test.mjs
else
  echo "note: node unavailable; the .test.mjs files run in the GitHub contracts check"
fi
# Native suites require the published OpenG2P runtime. GitHub's native-image
# step runs these independently; Jenkins requests this mode inside that image.
if [[ "${1:-source}" == --native ]]; then
  python -c 'import openg2p_registry_core'
  python -m pytest -q -p no:cacheprovider livestock-extension/tests "${COVERAGE[@]}"
fi
python ci/refactor/check_port.py . livestock
find ci ui/staff-ui/scripts -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
