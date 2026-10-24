"""The Docker images must extend the platform bundled in the pinned central chart."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def test_rp_pin_is_in_lockstep():
    pin=json.loads((ROOT/'ci/deploy/oan-chart.json').read_text())['registry']['platformVersion']
    pins={path.relative_to(ROOT).as_posix():match[1] for path in (ROOT/'docker').glob('*/Dockerfile')
          if (match:=re.search(r'^ARG RP_VERSION=(\S+)',path.read_text(encoding='utf-8'),re.M))}
    assert pins
    assert set(pins.values())=={pin}, pins
    jenkins=(ROOT/'Jenkinsfile').read_text(encoding='utf-8')
    override=re.search(r"RP_VERSION\s*=\s*'([^']+)'",jenkins)
    assert not override or override[1]==pin, 'Jenkins overrides the central platform contract'
