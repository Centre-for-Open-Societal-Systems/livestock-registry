"""Reject wrong/corrupt/unapproved central packages before environment changes."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import yaml

MODULE = Path(__file__).parents[1] / "ci/deploy/oan_chart.py"
if not MODULE.exists():
    MODULE = Path(__file__).with_name("oan_chart.py")
spec = importlib.util.spec_from_file_location("tested_oan_chart",MODULE)
chart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chart)

class CentralChartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"package.tgz"
        self.pin = {"repository":"https://raw.githubusercontent.com/Centre-for-Open-Societal-Systems/oan-helm/"+"a"*40+"/repository/",
            "name":"openg2p-example-registry","version":"1.0.0-dev.8","platformVersion":"1.2.2-rc.557",
            "promotionReady":False,"environment":"dev"}

    def package(self, *, child_version="1.2.2-rc.557", name=None, gate=True):
        info={"name":name or self.pin["name"],"version":self.pin["version"],"appVersion":self.pin["platformVersion"],
            "dependencies":[{"name":"openg2p-registry","alias":"registry","repository":"https://openg2p.github.io/openg2p-helm","version":self.pin["platformVersion"]}]}
        files={"Chart.yaml":yaml.safe_dump(info),"charts/openg2p-registry/Chart.yaml":yaml.safe_dump({"name":"openg2p-registry","version":child_version})}
        if gate:files["templates/refactor-promotion-gate.yaml"]='{{- fail "develop-refactor is incomplete: acceptance required" -}}'
        with tarfile.open(self.path,"w:gz") as archive:
            for name,body in files.items():
                payload=body.encode(); item=tarfile.TarInfo(self.pin["name"]+"/"+name); item.size=len(payload)
                archive.addfile(item,io.BytesIO(payload))
        self.pin["sha256"]=hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_valid_locked_package_retains_blocking_gate(self):
        self.package(); self.assertEqual(chart.verify(self.path,self.pin),self.pin)
    def test_changed_archive_is_rejected(self):
        self.package(); self.path.write_bytes(self.path.read_bytes()+b"changed")
        with self.assertRaisesRegex(ValueError,"checksum"):chart.verify(self.path,self.pin)
    def test_wrong_child_platform_is_rejected_even_when_checksum_matches(self):
        self.package(child_version="1.2.2-rc.544")
        with self.assertRaisesRegex(ValueError,"native platform"):chart.verify(self.path,self.pin)
    def test_wrong_registry_chart_is_rejected(self):
        self.package(name="openg2p-unrelated-registry")
        with self.assertRaisesRegex(ValueError,"name/version"):chart.verify(self.path,self.pin)
    def test_mutable_repository_ref_is_rejected(self):
        self.package(); self.pin["repository"]=self.pin["repository"].replace("a"*40,"main")
        with self.assertRaisesRegex(ValueError,"immutable"):chart.url(self.pin)
    def test_missing_render_gate_is_rejected(self):
        self.package(gate=False)
        with self.assertRaises(KeyError):chart.verify(self.path,self.pin)
    def test_deployment_is_blocked_before_any_environment_operation(self):
        self.package()
        with self.assertRaisesRegex(ValueError,"Deployment blocked"):chart.require_deployable(self.pin,"dev")
    def test_is_deployable_reports_without_raising(self):
        self.package()
        self.assertFalse(chart.is_deployable(self.pin,"dev"))
        self.pin["promotionReady"]=True
        self.assertTrue(chart.is_deployable(self.pin,"dev"))
        self.assertFalse(chart.is_deployable(self.pin,"staging"))
    def test_is_deployable_still_rejects_invalid_pin(self):
        self.package()
        self.pin["repository"]=self.pin["repository"].replace("a"*40,"main")
        with self.assertRaisesRegex(ValueError,"immutable"):chart.is_deployable(self.pin,"dev")
    def test_dev_approval_does_not_authorize_staging(self):
        self.package(); self.pin["promotionReady"]=True
        with self.assertRaisesRegex(ValueError,"Deployment blocked"):chart.require_deployable(self.pin,"staging")

    def test_verified_prefetched_archive_works_without_network(self):
        self.package()
        cache=Path(self.temp.name)/'cache'
        target=cache/self.pin['sha256']/(self.pin['name']+'-'+self.pin['version']+'.tgz')
        target.parent.mkdir(parents=True)
        target.write_bytes(self.path.read_bytes())
        with patch.object(chart,'CENTRAL_CACHE',cache), patch.object(chart.urllib.request,'urlopen',side_effect=AssertionError('Deploy node must remain offline')):
            result=chart.fetch(self.pin,Path(self.temp.name)/'deploy')
            self.assertEqual(result.read_bytes(),self.path.read_bytes())

    def test_corrupt_prefetched_archive_fails_without_network_fallback(self):
        self.package()
        cache=Path(self.temp.name)/'cache'
        target=cache/self.pin['sha256']/(self.pin['name']+'-'+self.pin['version']+'.tgz')
        target.parent.mkdir(parents=True)
        target.write_bytes(b'corrupt')
        with patch.object(chart,'CENTRAL_CACHE',cache), patch.object(chart.urllib.request,'urlopen',side_effect=AssertionError('No fallback')):
            with self.assertRaisesRegex(ValueError,'checksum'):
                chart.fetch(self.pin,Path(self.temp.name)/'deploy')

if __name__=="__main__":unittest.main()
