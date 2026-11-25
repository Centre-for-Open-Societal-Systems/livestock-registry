"""The Docker images must extend the platform bundled in the pinned central chart."""
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def test_rp_pin_is_in_lockstep():
    pin=json.loads((ROOT/'ci/deploy/oan-chart.json').read_text())['registry']['platformVersion']
    pins={path.relative_to(ROOT).as_posix():match[1] for path in (ROOT/'docker').glob('*/Dockerfile')
          if (match:=re.search(r'^ARG RP_VERSION=(\S+)',path.read_text(encoding='utf-8'),re.M))}
    assert pins
    assert set(pins.values())=={pin}, pins
    jenkins=(ROOT/'Jenkinsfile').read_text(encoding='utf-8') + (ROOT/'ci/pipelines/dev.groovy').read_text(encoding='utf-8')
    override=re.search(r"RP_VERSION\s*=\s*'([^']+)'",jenkins)
    assert not override or override[1]==pin, 'Jenkins overrides the central platform contract'

# The files that name the platform version outside the chart: what CI runs (the pipelines, the test image, the
# refactor checks and probes) and the images. scripts/bump-rp-version.sh moves every copy in these files.
PLATFORM_FILES=('Jenkinsfile','ci/pipelines/*.groovy','ci/refactor/*','docker/*/Dockerfile')
VERSION=re.compile(r'\b\d+\.\d+\.\d+-rc\.\d+\b')

def platform_copies(root):
    """{file: platform versions it names} for every file in PLATFORM_FILES."""
    return {path.relative_to(root).as_posix():set(VERSION.findall(path.read_text(encoding='utf-8')))
            for pattern in PLATFORM_FILES for path in sorted(root.glob(pattern)) if path.is_file()}

def test_every_platform_copy_follows_the_pin():
    pin=json.loads((ROOT/'ci/deploy/oan-chart.json').read_text())['registry']['platformVersion']
    chart=(ROOT/'helm/openg2p-livestock-registry/Chart.yaml').read_text(encoding='utf-8')
    assert re.search(r'^appVersion: (\S+)$',chart,re.M)[1]==pin
    assert re.search(r'- name: openg2p-registry\n(?:  .*\n)*?  version: (\S+)',chart)[1]==pin
    copies=platform_copies(ROOT)
    assert {'ci/pipelines/dev.groovy','ci/refactor/profile-tests.Dockerfile','ci/refactor/check_port.py'}<={
        name for name,versions in copies.items() if versions}
    stale={name:sorted(versions) for name,versions in copies.items() if versions-{pin}}
    assert not stale, stale

def test_bump_moves_every_copy_to_the_pin(tmp_path):
    for name in ['scripts/bump-rp-version.sh','ci/deploy/oan_chart.py','ci/deploy/oan-chart.json',*platform_copies(ROOT)]:
        (tmp_path/name).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy(ROOT/name,tmp_path/name)
    profile=tmp_path/'ci/deploy/oan-chart.json'
    pins=json.loads(profile.read_text())
    pins['registry']['platformVersion']='1.2.2-rc.700'
    profile.write_text(json.dumps(pins))
    subprocess.run(['bash','scripts/bump-rp-version.sh'],cwd=tmp_path,check=True,capture_output=True)
    copies=platform_copies(tmp_path)
    assert {name:sorted(versions) for name,versions in copies.items() if versions-{'1.2.2-rc.700'}}=={}
    assert copies['ci/pipelines/dev.groovy']=={'1.2.2-rc.700'}
