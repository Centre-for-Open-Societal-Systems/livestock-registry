#!/usr/bin/env bash
# Update central chart/dependency first, then pin its exact immutable artifact here.
# This command aligns local Dockerfiles with that reviewed profile; it never
# resolves a moving latest version or edits centrally owned chart sources.
set -euo pipefail
version="$(python3 ci/deploy/oan_chart.py platform registry)"
check=false
if [[ "${1:-}" == -n || "${1:-}" == --check || "${1:-}" == --dry-run ]]; then check=true; shift; fi
if [[ -n "${1:-}" && "$1" != "$version" ]]; then
  echo "Update the central chart/profile to the requested platform before changing images." >&2
  exit 1
fi
if $check; then echo "$version"; exit 0; fi
python3 - "$version" <<'PY'
from pathlib import Path
import re,sys
version=sys.argv[1]
# Every platform version these files name: the Dockerfiles' ARG RP_VERSION, the RP_VERSION in dev.groovy, the
# openg2p/openg2p-registry-* image tags the pipeline and the test image run, and the refactor checks and probes.
# test/test_rp_pin_lockstep.py (PLATFORM_FILES) checks the same files.
for pattern in ('Jenkinsfile','ci/pipelines/*.groovy','ci/refactor/*','docker/*/Dockerfile'):
    for path in sorted(Path('.').glob(pattern)):
        if path.is_file():
            body=path.read_text(encoding='utf-8')
            path.write_text(re.sub(r'\b\d+\.\d+\.\d+-rc\.\d+\b',version,body),encoding='utf-8')
PY
echo "Images aligned to central platform $version; review the diff before committing."
