"""Adversarial checks for the deployment routing guard (stdlib only)."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('guard',Path(__file__).resolve().parents[1]/'ci/check-new-dev-routes.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


class RoutingGuardTests(unittest.TestCase):
    def manifest(self,registry='crop'):
        release='cropsown-registry' if registry=='crop' else 'livestock-registry'
        hosts={release+'-staff-portal-ui':registry+'-registry',release+'-staff-portal-api':'staff-'+registry,release+'-partner-api':'partner-'+registry}
        if registry=='livestock':hosts[release+'-id-generator']='idgenerator-livestock'
        return {'kind':'List','items':[{'kind':'VirtualService','metadata':{'name':name},'spec':{'hosts':[host+'.development.oanstaging.com'],'gateways':['istio-system/development']}} for name,host in hosts.items()]},release

    def test_canonical_routes_and_private_dashboard_pass(self):
        for registry in ['crop','livestock']:
            data,release=self.manifest(registry)
            data['items'].append({'kind':'VirtualService','metadata':{'name':'private-dashboard'},'spec':{'hosts':['dashboard-api.'+registry+'.openg2p.test'],'gateways':['internal']}})
            self.assertEqual(guard.check(data,registry,release,registry)['routingGuard'],'passed')

    def test_actual_outage_combination_rejected(self):
        data,release=self.manifest()
        for route in data['items']:
            route['spec']['hosts']=[route['spec']['hosts'][0].replace('.development.','-development.')]
            route['spec']['gateways']=['internal']
        with self.assertRaises(AssertionError):guard.check(data,'crop',release,'crop')

    def test_kubectl_json_stream_and_list_both_accepted(self):
        data,release=self.manifest()
        for raw in [json.dumps(data),'\n'.join(json.dumps(d) for d in data['items'])]:
            parsed=guard.load_resources(io.StringIO(raw))
            self.assertEqual(guard.check(parsed,'crop',release,'crop')['routingGuard'],'passed')

    def test_empty_or_truncated_kubectl_output_fails(self):
        data,release=self.manifest()
        with self.assertRaises(AssertionError):guard.check(guard.load_resources(io.StringIO('')),'crop',release,'crop')
        with self.assertRaises(ValueError):guard.load_resources(io.StringIO(json.dumps(data)+'\n{"kind":'))

    def test_correct_host_wrong_gateway_rejected(self):
        data,release=self.manifest();data['items'][0]['spec']['gateways']=['internal']
        with self.assertRaises(AssertionError):guard.check(data,'crop',release,'crop')

    def test_missing_route_rejected(self):
        data,release=self.manifest();data['items'].pop()
        with self.assertRaises(AssertionError):guard.check(data,'crop',release,'crop')

    def test_legacy_encoded_login_configuration_rejected(self):
        data,release=self.manifest()
        data['items'].append({'kind':'Secret','data':{'login.json':base64.b64encode(b'{"issuer":"https://keycloak-development.oanstaging.com/realms/staff"}').decode()}})
        with self.assertRaises(AssertionError):guard.check(data,'crop',release,'crop')

    def test_cookie_regression_rejected(self):
        for value in [{'COOKIE_DOMAIN':'.oanstaging.com'},{'name':'IAM_STAFF_AUTH_COOKIE_DOMAIN','value':'.oanstaging.com'}]:
            data,release=self.manifest();data['items'].append({'kind':'ConfigMap','data':value})
            with self.assertRaises(AssertionError):guard.check(data,'crop',release,'crop')

    def test_private_dashboard_must_not_become_public(self):
        data,release=self.manifest()
        data['items'].append({'kind':'VirtualService','metadata':{'name':'private-dashboard'},'spec':{'hosts':['dashboard-api.crop.openg2p.test'],'gateways':['istio-system/development']}})
        with self.assertRaises(AssertionError):guard.check(data,'crop',release,'crop')

    def test_other_namespace_rejected(self):
        data,release=self.manifest();data['items'][0]['metadata']['namespace']='farmer'
        with self.assertRaises(AssertionError):guard.check(data,'crop',release,'crop')


if __name__=='__main__':unittest.main()
