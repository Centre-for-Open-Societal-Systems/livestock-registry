#!/usr/bin/env bash
set -euo pipefail
python3 ci/deploy/oan_chart.py version registry
python3 ci/deploy/oan_chart.py platform registry
