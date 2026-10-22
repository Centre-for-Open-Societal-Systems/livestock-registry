"""Prevent the observed CI reset and mismatched signing-key deployments."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('enrichment_guard', ROOT / 'ci/check-farmer-enrichment.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class FarmerEnrichmentDeploymentTests(unittest.TestCase):
    def manifest(self):
        values = {name: 'configured' for name in guard.REQUIRED}
        values.update(ENRICHMENT_ENABLED='true',
                      DCI_SEARCH_URL='http://farmer-api.farmer.svc.cluster.local/dci/registry/sync/search',
                      SIGNING_KEY_KID='test-kid', SIGNING_ALGORITHM='EdDSA')
        env = [{'name': guard.PREFIX + name, 'value': value} for name, value in values.items()]
        env.append({'name': guard.PREFIX + 'SIGNING_KEY', 'valueFrom': {
            'secretKeyRef': {'name': 'lookup-key', 'key': 'private-key.pem'}}})
        self.env = env
        return [{'kind': 'Deployment', 'metadata': {'name': 'staff-api', 'namespace': 'livestock'},
                 'spec': {'template': {'spec': {'containers': [{'name': 'staff-portal-api', 'env': env}]}}}}]

    def secret(self, namespace='livestock', name='lookup-key'):
        return {'metadata': {'namespace': namespace}, 'data': {
            key: base64.b64encode(value.encode()).decode() for key, value in {
                'private-key.pem': 'test private key', 'kid': 'test-kid', 'algorithm': 'EdDSA'}.items()}}

    def check(self, items, loader=None):
        return guard.check(items, 'staff-api', 'livestock', loader)

    def test_complete_config_and_secret_pass(self):
        self.assertTrue(self.check(self.manifest(), self.secret)['liveSecretChecked'])

    def test_original_reset_is_rejected(self):
        items = self.manifest()
        self.env[:] = [{'name': guard.PREFIX + 'ENRICHMENT_ENABLED', 'value': 'false'}]
        with self.assertRaisesRegex(AssertionError, 'disabled'):
            self.check(items)

    def test_each_missing_required_setting_is_rejected(self):
        for name in guard.REQUIRED:
            with self.subTest(name=name):
                items = self.manifest()
                self.env[:] = [entry for entry in self.env if entry['name'] != guard.PREFIX + name]
                with self.assertRaisesRegex(AssertionError, 'missing'):
                    self.check(items)

    def test_inline_optional_and_missing_private_key_rejected(self):
        variants = [{'value': 'do-not-print'}, {'valueFrom': {'secretKeyRef': {
            'name': 'lookup-key', 'key': 'private-key.pem', 'optional': True}}}, {}]
        for variant in variants:
            items = self.manifest()
            self.env[-1] = {'name': guard.PREFIX + 'SIGNING_KEY', **variant}
            with self.assertRaises(AssertionError):
                self.check(items)

    def test_missing_secret_and_mismatched_key_metadata_rejected(self):
        for field in ['private-key.pem', 'kid', 'algorithm']:
            items = self.manifest()
            secret = self.secret()
            secret['data'][field] = base64.b64encode(b'' if field == 'private-key.pem' else b'wrong').decode()
            with self.assertRaises(AssertionError):
                self.check(items, lambda *_: secret)
        def unavailable(*_):
            raise AssertionError('Required signing Secret is unavailable')
        with self.assertRaisesRegex(AssertionError, 'unavailable'):
            self.check(self.manifest(), unavailable)

    def test_wrong_namespace_duplicate_env_and_duplicate_deployment_rejected(self):
        items = self.manifest()
        items[0]['metadata']['namespace'] = 'live'
        with self.assertRaises(AssertionError):
            self.check(items)
        items = self.manifest()
        self.env.append(self.env[0])
        with self.assertRaises(AssertionError):
            self.check(items)
        items = self.manifest()
        with self.assertRaises(AssertionError):
            self.check(items + items)

    def test_empty_and_truncated_input_rejected(self):
        with self.assertRaises(AssertionError):
            self.check(guard.resources(io.StringIO('')))
        with self.assertRaises(ValueError):
            guard.resources(io.StringIO('{"kind":'))
        items = self.manifest()
        for raw in [json.dumps({'kind': 'List', 'items': items}), json.dumps(items[0])]:
            self.assertEqual(self.check(guard.resources(io.StringIO(raw)))['farmerEnrichmentGuard'], 'passed')

    def test_invalid_lookup_url_and_nonfinite_timeout_rejected(self):
        for name, value in [('DCI_SEARCH_URL', 'http://farmer-api/wrong-path'),
                            ('TIMEOUT_SECONDS', 'nan'), ('TIMEOUT_SECONDS', '-1')]:
            items = self.manifest()
            self.env[:] = [entry for entry in self.env if entry['name'] != guard.PREFIX + name]
            self.env.append({'name': guard.PREFIX + name, 'value': value})
            with self.assertRaises(AssertionError):
                self.check(items)


if __name__ == '__main__':
    unittest.main()
