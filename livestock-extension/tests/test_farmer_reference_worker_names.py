"""The AWE outbox worker has its new task and beat names; the old task name still runs the same function.

The worker module needs the native Celery runtime to import, so this reads its source instead; the
loader probe (ci/refactor/onboarding_probe.py) checks the registered names in the real runtime.
"""
import importlib
import os
import re
import sys
import unittest
from pathlib import Path

PACKAGE = os.environ.get("REGISTRY_EXTENSION_MODULE", "openg2p_registry_livestock_extension")
sys.modules.setdefault("openg2p_registry_extensions", importlib.import_module(PACKAGE))
SOURCE = (Path(importlib.import_module(PACKAGE).__file__).parent / "farmer_reference/worker.py").read_text(encoding="utf-8")


class WorkerNameTests(unittest.TestCase):
    def test_new_and_old_task_names_are_registered_for_one_function(self):
        self.assertIn('TASK_NAME = "farmer_reference_awe_outbox_worker"', SOURCE)
        self.assertIn('LEGACY_TASK_NAME = "coss.farmer_reference.deliver_workflows"', SOURCE)
        registered = re.findall(r"shared_task\(name=(\w+), queue=_worker_queue\)\(deliver_workflows\)", SOURCE)
        self.assertEqual(sorted(registered), ["LEGACY_TASK_NAME", "TASK_NAME"])

    def test_beat_sends_the_new_name_only(self):
        self.assertRegex(SOURCE, r'"farmer-reference-awe-outbox-beat-producer": \{\s+"task": TASK_NAME,')
        self.assertNotIn("coss-farmer-reference-workflows", SOURCE)


if __name__ == "__main__":
    unittest.main()
