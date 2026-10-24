"""Exercise rejected deployment configurations without a cluster or credentials."""
import base64
import copy
import importlib.util
from pathlib import Path
import unittest

MODULE=Path(__file__).resolve().parents[1]/'ci/refactor/deployment_guard.py'
if not MODULE.exists(): MODULE=Path(__file__).with_name('deployment_guard.py')
spec=importlib.util.spec_from_file_location('deployment_guard',MODULE)
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class DeploymentGuardTests(unittest.TestCase):
    def setUp(self):
        env=[{'name':guard.PREFIX+name,'value':'verification'} for name in guard.REQUIRED]
        for item in env:
            if item['name'].endswith(('DCI_URL','AWE_TOKEN_URL')): item['value']='https://verification.invalid/native'
        env += [{'name':guard.PREFIX+name,'value':'/config/'+name} for name in guard.FILES]
        secret={'secretName':'verification-secret','items':[{'key':name,'path':name} for name in guard.FILES]}
        container={'env':env,'volumeMounts':[{'name':'config','mountPath':'/config','readOnly':True}]}
        self.items=[]
        for suffix in ('staff-portal-api','celery-worker','celery-beat-producer'):
            one=copy.deepcopy(container)
            one['name']=suffix
            self.items.append({'kind':'Deployment','metadata':{'name':'registry-'+suffix,'namespace':'verification'},
                'spec':{'template':{'spec':{'containers':[one],'volumes':[{'name':'config','secret':secret}]}}}})

    def test_valid_role_configuration_and_secret_readback(self):
        data={name:base64.b64encode(b'non-secret-test-fixture').decode() for name in guard.FILES}
        result=guard.check(self.items,'registry','verification',lambda ns,name:{'metadata':{'namespace':ns},'data':data})
        self.assertEqual(len(result['deployments']),3)
        self.assertTrue(result['liveSecretsChecked'])

    def test_missing_worker_configuration_is_rejected(self):
        self.items[1]['spec']['template']['spec']['containers'][0]['env'].pop()
        with self.assertRaisesRegex(AssertionError,'setting missing'): guard.check(self.items,'registry','verification')

    def test_private_file_cannot_come_from_configmap(self):
        volume=self.items[0]['spec']['template']['spec']['volumes'][0]
        volume['configMap']={'name':'unsafe'}
        del volume['secret']
        with self.assertRaisesRegex(AssertionError,'Secret/ConfigMap volume missing'): guard.check(self.items,'registry','verification')

    def test_query_secret_url_is_rejected(self):
        self.items[0]['spec']['template']['spec']['containers'][0]['env'][0]['value']='https://verification.invalid/native?secret=fixture'
        with self.assertRaisesRegex(AssertionError,'service URL'): guard.check(self.items,'registry','verification')

    def test_cross_namespace_is_rejected(self):
        self.items[0]['metadata']['namespace']='another'
        with self.assertRaisesRegex(AssertionError,'namespace'): guard.check(self.items,'registry','verification')

    def test_empty_secret_key_is_rejected(self):
        with self.assertRaisesRegex(AssertionError,'Secret key empty or missing'):
            guard.check(self.items,'registry','verification',lambda ns,name:{'metadata':{'namespace':ns},'data':{}})


if __name__=='__main__': unittest.main()
