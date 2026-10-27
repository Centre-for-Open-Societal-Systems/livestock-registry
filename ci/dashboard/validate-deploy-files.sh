#!/usr/bin/env bash
set -euo pipefail
registry=${1:?registry required}
case "$registry" in cropsown|livestock) ;; *) echo 'Unknown registry' >&2; exit 1 ;; esac
for file in ci/deploy/oan_chart.py ci/deploy/oan-chart.json ci/dashboard/deploy-ui.sh; do
  test -s "$file" || { echo "Required central deployment consumer missing: $file" >&2; exit 1; }
done
python3 ci/deploy/oan_chart.py url dashboard >/dev/null
python3 - "$registry" <<'PY'
import json,sys
pin=json.load(open('ci/deploy/oan-chart.json'))['dashboard']
assert pin['name']==sys.argv[1]+'-registry-dashboard', 'Wrong dashboard ownership'
assert pin['environment']=='dev', 'Separate staging preservation acceptance is required'
PY
