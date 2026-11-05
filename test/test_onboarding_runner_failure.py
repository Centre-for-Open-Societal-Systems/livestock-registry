"""Failed or timed-out orchestration must never certify a complete run."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE=Path(__file__).resolve().parents[1]/'ci/refactor/verify_onboarding.py'
spec=importlib.util.spec_from_file_location('onboarding_runner',MODULE)
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerFailureTests(unittest.TestCase):
    def fixture(self,directory):
        root=Path(directory)
        (root/'cropsown-extension/src').mkdir(parents=True)
        (root/'ci/refactor').mkdir(parents=True)
        (root/'ci/refactor/check_port.py').write_text('# fixture only\n')
        return root

    def test_failing_command_leaves_incomplete_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.fixture(tmp)
            failed=subprocess.CompletedProcess(['fixture'],7,'','synthetic failure')
            with patch.object(runner,'ROOT',root),patch.object(runner.subprocess,'run',return_value=failed):
                with self.assertRaisesRegex(RuntimeError,'source-check:'): runner.main('cropsown')
            report=json.loads((root/'ci-output/refactor/ONBOARDING_VERIFICATION.json').read_text())
            self.assertFalse(report['verification_complete'])
            self.assertEqual(report['steps'][0]['result'],'FAIL')

    def test_timeout_is_explicit_failure_and_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.fixture(tmp)
            with patch.object(runner,'ROOT',root),patch.object(runner.subprocess,'run',side_effect=subprocess.TimeoutExpired(['fixture'],180)):
                with self.assertRaises(subprocess.TimeoutExpired): runner.main('cropsown')
            report=json.loads((root/'ci-output/refactor/ONBOARDING_VERIFICATION.json').read_text())
            self.assertFalse(report['verification_complete'])
            self.assertEqual(report['steps'][0]['result'],'FAIL')
            self.assertEqual(report['steps'][0]['error_type'],'TimeoutExpired')


if __name__=='__main__': unittest.main()
