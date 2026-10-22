"""Render real dashboard templates, hooks and the files sent to the deploy node."""
import fnmatch
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = next(name for name in ('cropsown', 'livestock') if (ROOT / f'helm/{name}-registry-dashboard').is_dir())
CHART = ROOT / f'helm/{REGISTRY}-registry-dashboard'
VALUES = ROOT / 'helm/environments/dev/dashboard-ui.yaml'
REPOSITORY = f'123456789012.dkr.ecr.ap-south-1.amazonaws.com/oan/{REGISTRY}-registry/dashboard-ui'
pytestmark = pytest.mark.skipif(not shutil.which('helm'), reason='Helm required')

def mappings(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from mappings(child)

def render(chart, values, *extra):
    result = subprocess.run(['helm', 'template', REGISTRY+'-registry-dashboard', str(chart), '-n', 'crop' if REGISTRY == 'cropsown' else 'livestock', '-f', str(values), *extra], check=True, capture_output=True, text=True)
    return [d for d in yaml.safe_load_all(result.stdout) if d]

def valid_labels(documents):
    for document in documents:
        for node in mappings(document):
            for key, value in node.get('metadata', {}).get('labels', {}).items():
                assert isinstance(value, str), (document['kind'], key, value)
                assert len(value) <= 63 and re.fullmatch(r'(?:[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?)?', value), (document['kind'], key, value)

@pytest.mark.parametrize('tag,version', [
    ('012345abcdef@sha256:'+'a'*64, '012345abcdef'),
    ('012345abcdef', '012345abcdef'),
    ('a'*128, 'a'*63),
    ('_release.-', 'release'),
    ('a'*62+'-tail', 'a'*62),
])
def test_digest_pins_and_semver_metadata_on_every_resource_and_hook(tmp_path, tag, version):
    chart = tmp_path / 'chart'
    shutil.copytree(CHART, chart)
    metadata = yaml.safe_load((chart/'Chart.yaml').read_text())
    metadata['version'] = '1.0.0+build-regression'
    (chart/'Chart.yaml').write_text(yaml.safe_dump(metadata))
    documents = render(chart, VALUES, '--set-string', 'image.repository='+REPOSITORY, '--set-string', 'image.tag='+tag)
    valid_labels(documents)
    hooks = [d for d in documents if 'helm.sh/hook' in d['metadata'].get('annotations', {})]
    assert {d['kind'] for d in hooks} == {'ServiceAccount', 'Role', 'RoleBinding', 'Job'}
    images, versions = [], []
    for d in documents:
        for node in mappings(d):
            if node.get('image', '').startswith(REPOSITORY+':'):
                images.append(node['image'])
            label = node.get('metadata', {}).get('labels', {}).get('app.kubernetes.io/version')
            if label is not None:
                versions.append(label)
    assert len(images) == 3 and set(images) == {REPOSITORY+':'+tag}
    assert set(versions) == {version}
    setup = next(d for d in documents if d['metadata']['name'].endswith('-iam-setup'))
    env = {e['name']: e.get('value') for e in setup['spec']['template']['spec']['containers'][0]['env']}
    assert env['GRANT_USERS'] == 'admin' and env['DASHBOARD_API_ROLE'] == 'charts:read'

def test_api_chart_label_accepts_semver_build_metadata_without_changing_image(tmp_path):
    source = ROOT / f'helm/openg2p-{REGISTRY}-registry'
    chart = tmp_path / 'api-chart'
    (chart/'templates').mkdir(parents=True)
    (chart/'Chart.yaml').write_text(yaml.safe_dump({'apiVersion':'v2','name':f'openg2p-{REGISTRY}-registry','version':'1.2.0+regression'}))
    shutil.copyfile(source/'values.yaml', chart/'values.yaml')
    for name in ('dashboard-api.yaml', '_reporting.tpl'):
        shutil.copyfile(source/'templates'/name, chart/'templates'/name)
    tag = 'regression@sha256:'+'b'*64
    documents = render(chart, chart/'values.yaml', '--set', 'dashboardApi.enabled=true', '--set', 'dashboardApi.auth.enabled=true', '--set-string', 'dashboardApi.auth.issuer=https://iam.example.test/realms/staff', '--set-string', 'dashboardApi.image.repository=example.test/dashboard-api', '--set-string', 'dashboardApi.image.tag='+tag)
    valid_labels(documents)
    deploy = next(d for d in documents if d['kind']=='Deployment')
    assert deploy['spec']['template']['spec']['containers'][0]['image']=='example.test/dashboard-api:'+tag

@pytest.mark.skipif(REGISTRY != 'cropsown', reason='Crop uses a deployment stash')
def test_clean_unstashed_workspace_contains_and_renders_dashboard(tmp_path):
    pipeline = (ROOT/'Jenkinsfile').read_text(encoding='utf-8')
    includes = re.search(r'stash name: \'deploy\', includes: "([^"]+)"', pipeline).group(1)
    patterns = includes.replace('${HELM_CHART_DIR}', 'helm/openg2p-cropsown-registry').split(',')
    tracked = subprocess.run(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard'],check=True,capture_output=True,text=True).stdout.splitlines()
    for name in tracked:
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
            dest=tmp_path/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,dest)
    for name in ('ci/dashboard/deploy-ui.sh','ci/dashboard/validate-deploy-files.sh','helm/cropsown-registry-dashboard/Chart.yaml','helm/environments/dev/dashboard-ui.yaml'):
        assert (tmp_path/name).is_file(), name
    assert "sh 'bash ci/dashboard/validate-deploy-files.sh cropsown'" in pipeline
    valid_labels(render(tmp_path/'helm/cropsown-registry-dashboard',tmp_path/'helm/environments/dev/dashboard-ui.yaml','--set-string','image.repository='+REPOSITORY,'--set-string','image.tag=regression@sha256:'+'c'*64))
