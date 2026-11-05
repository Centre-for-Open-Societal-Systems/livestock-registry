"""Reject deployments that disable or incompletely configure Farmer enrichment.

Accept kubectl JSON on stdin. --check-live-secret also checks the referenced
Secret in the target namespace without printing its contents.
"""
import argparse
import base64
import json
import math
import subprocess
import sys
from urllib.parse import urlsplit

PREFIX = 'FARMER_REGISTRY_'
REQUIRED = (
    'DCI_SEARCH_URL', 'SENDER_ID', 'RECEIVER_ID', 'SIGNING_KEY_KID',
    'SIGNING_ALGORITHM', 'CONSENT_AUDIENCE', 'CONSENT_DATA_CONTROLLER',
    'CONSENT_SCOPES', 'CONSENT_PURPOSE',
)


def resources(stream):
    decoder = json.JSONDecoder()
    text = stream.read().strip()
    items = []
    while text:
        document, end = decoder.raw_decode(text)
        items.extend(document.get('items', []) if document.get('kind') == 'List' else [document])
        text = text[end:].lstrip()
    return items


def check(items, deployment, namespace, secret_loader=None):
    targets = [item for item in items if item.get('kind') == 'Deployment'
               and item.get('metadata', {}).get('name') == deployment]
    assert len(targets) == 1, 'Expected exactly one staff API Deployment'
    target = targets[0]
    assert target['metadata'].get('namespace', namespace) == namespace, 'Wrong target namespace'
    containers = target['spec']['template']['spec']['containers']
    staff = [container for container in containers if container['name'] == 'staff-portal-api']
    assert len(staff) == 1, 'Staff API container missing or duplicated'
    entries = staff[0].get('env', [])
    env = {entry['name']: entry for entry in entries}
    assert len(env) == len(entries), 'Duplicate environment variables'

    def value(name):
        return str(env.get(PREFIX + name, {}).get('value', '')).strip()

    assert value('ENRICHMENT_ENABLED').lower() in {'true', '1', 'yes'}, 'Farmer enrichment is disabled'
    for name in REQUIRED:
        assert value(name), 'Required lookup setting missing: ' + PREFIX + name
    url = urlsplit(value('DCI_SEARCH_URL'))
    assert url.scheme in {'http', 'https'} and url.hostname and url.path == '/dci/registry/sync/search', 'Invalid Farmer lookup URL'
    timeout = float(value('TIMEOUT_SECONDS') or '10')
    assert math.isfinite(timeout) and timeout > 0, 'Invalid Farmer lookup timeout'
    key = env.get(PREFIX + 'SIGNING_KEY', {})
    assert 'value' not in key, 'Private signing key must come from a Secret'
    ref = key.get('valueFrom', {}).get('secretKeyRef', {})
    assert ref.get('name') and ref.get('key') and not ref.get('optional'), 'Required signing Secret reference missing'

    if secret_loader is not None:
        secret = secret_loader(namespace, ref['name'])
        assert secret.get('metadata', {}).get('namespace') == namespace, 'Signing Secret is in the wrong namespace'
        data = secret.get('data', {})
        assert base64.b64decode(data.get(ref['key'], ''), validate=True).strip(), 'Signing Secret private key is empty'
        for field, setting in [('kid', 'SIGNING_KEY_KID'), ('algorithm', 'SIGNING_ALGORITHM')]:
            actual = base64.b64decode(data.get(field, ''), validate=True).decode().strip()
            assert actual == value(setting), 'Signing Secret metadata disagrees with lookup setting: ' + setting
    return {'farmerEnrichmentGuard': 'passed', 'deployment': deployment,
            'namespace': namespace, 'liveSecretChecked': secret_loader is not None}


def live_secret(namespace, name):
    result = subprocess.run(['kubectl', 'get', 'secret', name, '-n', namespace, '-o', 'json'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, 'Required signing Secret is unavailable'
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deployment', required=True)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--check-live-secret', action='store_true')
    args = parser.parse_args()
    try:
        report = check(resources(sys.stdin), args.deployment, args.namespace,
                       live_secret if args.check_live_secret else None)
    except (AssertionError, ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as error:
        # Do not print parser errors, subprocess output, or Secret contents.
        reason = str(error) if isinstance(error, AssertionError) else 'Invalid enrichment configuration or unavailable Secret'
        print('Farmer enrichment guard failed: ' + reason, file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
