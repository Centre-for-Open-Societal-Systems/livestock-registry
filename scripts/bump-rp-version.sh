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
for path in (Path('docker')).glob('*/Dockerfile'):
    body=path.read_text()
    if re.search(r'^ARG RP_VERSION=',body,re.M):
        path.write_text(re.sub(r'^ARG RP_VERSION=.*', 'ARG RP_VERSION='+version,body,flags=re.M))
path=Path('Jenkinsfile')
body=path.read_text(encoding='utf-8')
path.write_text(re.sub(r"(RP_VERSION\s*=\s*')[^']+",r'\g<1>'+version,body),encoding='utf-8')
PY
echo "Images aligned to central platform $version; review the diff before committing."
