"""Image names: eoan/livestock-registry/<image>[-<rpVersion>]:<version>-<branch>.<build>. version from init.yaml,
rpVersion from Chart.yaml appVersion, which every platform Dockerfile's ARG RP_VERSION default must equal.

Standard library only (runs on the Jenkins agent's stock Python).
    python3 -m unittest discover -s test -p test_image_names.py -v
"""
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("image_names", ROOT / "ci/image_names.py")
image_names = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image_names)
CHART = (ROOT / "helm/openg2p-livestock-registry/Chart.yaml").read_text(encoding="utf-8")
RP = re.search(r"(?m)^appVersion: (\S+)$", CHART).group(1)
VERSION = re.search(r"(?m)^version: (\S+)$", (ROOT / "init.yaml").read_text(encoding="utf-8")).group(1)
PLATFORM_DOCKERFILES = ("staff-api", "partner-api", "celery", "db-seed", "sanity-tests")


class ImageNameTests(unittest.TestCase):
    def test_platform_images_carry_the_platform_version_of_the_chart(self):
        for image in image_names.PLATFORM_IMAGES:
            self.assertEqual(image_names.repository(image), "eoan/livestock-registry/%s-%s" % (image, RP))

    def test_other_images_carry_no_platform_version(self):
        self.assertEqual(image_names.repository("registry-connector"), "eoan/livestock-registry/registry-connector-api")
        for image in ("registry-connector-api", "registry-connector-ui", "dashboard-api", "dashboard-ui"):
            self.assertEqual(image_names.repository(image), "eoan/livestock-registry/" + image)

    def test_an_unknown_image_has_no_name(self):
        for image in ("connector-service", "staff-api-1.2.2", ""):
            with self.assertRaises(ValueError):
                image_names.repository(image)

    def test_legacy_names_are_the_repositories_before_eoan(self):
        self.assertEqual(image_names.legacy("staff-api"), "openg2p/livestock-registry/staff-api")
        self.assertEqual(image_names.legacy("registry-connector-api"), "openg2p/livestock-registry/registry-connector")
        self.assertEqual(image_names.legacy("dashboard-ui"), "openg2p/livestock-registry/dashboard-ui")

    def test_init_yaml_holds_a_release_version(self):
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$")
        self.assertNotEqual(VERSION, "0.0.0")

    def test_init_yaml_refuses_pre_release_words_and_other_fields(self):
        for text in ("version: 1.0.0-rc.1\n", "version: 0.0\n", "", "version: 1.0.0\nrpVersion: 1.2.2\n",
                     "version: 1.0.0\nversion: 1.1.0\n"):
            with tempfile.TemporaryDirectory() as work:
                path = Path(work) / "init.yaml"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError, msg=text):
                    image_names.read_init(path)

    def test_every_platform_dockerfile_is_built_on_the_chart_platform_version(self):
        for name in PLATFORM_DOCKERFILES:
            text = (ROOT / "docker" / name / "Dockerfile").read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"(?m)^ARG RP_VERSION=(\S+)$", text), [RP], name)

    def test_tag_is_the_init_version_branch_and_build_number(self):
        self.assertEqual(image_names.tag("develop", 300), VERSION + "-develop.300")

    def test_tag_turns_any_branch_into_a_docker_tag(self):
        self.assertEqual(image_names.tag("feature/New_Field", "7"), VERSION + "-feature-new-field.7")

    def test_tag_refuses_a_missing_branch_or_build_number(self):
        for branch, build in (("develop", "0"), ("develop", ""), ("develop", "3a"), ("//", "5")):
            with self.assertRaises(ValueError):
                image_names.tag(branch, build)

    def test_command_line(self):
        for argv, expected in ((["tag", "develop", "12"], VERSION + "-develop.12"),
                               (["repository", "db-seed"], "eoan/livestock-registry/db-seed-" + RP),
                               (["legacy", "celery"], "openg2p/livestock-registry/celery"),
                               (["platform"], RP)):
            done = subprocess.run([sys.executable, str(ROOT / "ci/image_names.py")] + argv, stdout=subprocess.PIPE,
                                  universal_newlines=True, check=True)
            self.assertEqual(done.stdout, expected + "\n")


if __name__ == "__main__":
    unittest.main()
