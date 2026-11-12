"""Which connector images ci/connector/upgrade-livestock-connector-staging.sh pins, with stand-in aws, helm and kubectl
(no cluster, no network). PLAN_ONLY=1 stops the script after the diff and the dry run."""
import io
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "ci/connector/upgrade-livestock-connector-staging.sh"
PREFIX = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/openg2p/livestock-registry"
COMMIT = "b053d120c8e0" + "4" * 28
PROMOTED = "sha256:" + "d" * 64       # the staff-api digest the promoted chart pins
CONNECTOR = "sha256:" + "c" * 64
CONNECTOR_UI = "sha256:" + "e" * 64

HELM = """#!/usr/bin/env bash
case "$1" in
  list) echo '[{"status": "deployed", "chart": "openg2p-connector-0.1.0"}]' ;;
  get) echo "kind: Deployment" ;;
  template) echo "kind: Deployment" ;;
esac
exit 0
"""
KUBECTL = "#!/usr/bin/env bash\nexit 0\n"
# describe-images by digest prints that digest's tags; by tag, the digest that tag is on now. Tags come from TAGS
# ("<repository-suffix>:<tag>=<digest>" lines), the promoted digest's tags from DIGEST_TAGS.
AWS = """#!/usr/bin/env bash
repo= ; ids=
while [ $# -gt 0 ]; do
  case "$1" in --repository-name) repo=$2; shift ;; --image-ids) ids=$2; shift ;; esac
  shift
done
case "$ids" in
  imageDigest=*) printf '%s\\n' "$DIGEST_TAGS" ;;
  imageTag=*) line=$(printf '%s\\n' "$TAGS" | grep -F "${repo##*/}:${ids#imageTag=}=" | head -n 1)
              test -n "$line" || exit 254
              echo "${line#*=}" ;;
esac
"""


def chart_archive(path, source_commit):
    chart = "apiVersion: v2\nname: openg2p-livestock-registry\nversion: 1.0.0-rc.464\nannotations:\n"
    if source_commit:
        chart += f"  oan.org/source-commit: {source_commit}\n"
    values = f"registry:\n  staffApi:\n    image:\n      repository: {PREFIX}/staff-api\n      tag: 1.0.0-rc.464@{PROMOTED}\n"
    with tarfile.open(path, "w:gz") as bundle:
        for name, text in (("Chart.yaml", chart), ("values.yaml", values)):
            data = text.encode()
            info = tarfile.TarInfo(f"openg2p-livestock-registry/{name}")
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))


@unittest.skipUnless(shutil.which("bash") and shutil.which("python3"), "needs bash and python3")
class ConnectorBuildTagTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        (self.repo / "ci/connector").mkdir(parents=True)
        shutil.copy(ROOT / SCRIPT, self.repo / SCRIPT)
        (self.repo / "built-chart").mkdir()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        for name, body in (("helm", HELM), ("kubectl", KUBECTL), ("aws", AWS)):
            path = self.bin / name
            path.write_text(body, newline="\n")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def run_script(self, source_commit, digest_tags, tags):
        chart_archive(self.repo / "built-chart/openg2p-livestock-registry-1.0.0-rc.464.tgz", source_commit)
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], KUBECONFIG="/nonexistent",
                   PLAN_ONLY="1", DIGEST_TAGS=digest_tags, TAGS="\n".join(tags))
        done = subprocess.run(["bash", str(self.repo / SCRIPT)], cwd=str(self.repo), env=env,
                              capture_output=True, text=True)
        return done.returncode, done.stdout + done.stderr

    def test_a_rebuild_that_moved_the_tag_off_the_promoted_digest_still_finds_the_build(self):
        # Staging #17: the promoted digest keeps only the promotion tags; a later develop build of the same
        # commit carries the commit tag now, for staff-api and the connector images alike.
        code, out = self.run_script(COMMIT, "staging\t1.0.0-rc.464", [
            f"registry-connector:{COMMIT[:12]}={CONNECTOR}", f"registry-connector-ui:{COMMIT[:12]}={CONNECTOR_UI}"])
        self.assertEqual(code, 0, out)
        self.assertIn(f"Promoted chart is build {COMMIT[:12]} (chart commit {COMMIT[:12]};", out)
        self.assertIn(f"api, worker, beat: {PREFIX}/registry-connector@{CONNECTOR}", out)
        self.assertIn(f"ui: {PREFIX}/registry-connector-ui@{CONNECTOR_UI}", out)
        self.assertIn("PLAN_ONLY: nothing was changed.", out)

    def test_a_chart_without_the_commit_falls_back_to_the_digest_tag(self):
        code, out = self.run_script("", f"staging\t{COMMIT[:12]}", [
            f"registry-connector:{COMMIT[:12]}={CONNECTOR}", f"registry-connector-ui:{COMMIT[:12]}={CONNECTOR_UI}"])
        self.assertEqual(code, 0, out)
        self.assertIn(f"Promoted chart is build {COMMIT[:12]} (chart commit none recorded;", out)

    def test_no_build_tag_anywhere_fails_before_the_cluster(self):
        code, out = self.run_script("", "staging\t1.0.0-rc.464", [])
        self.assertNotEqual(code, 0)
        self.assertIn("Neither the promoted chart (oan.org/source-commit) nor staff-api", out)
        self.assertNotIn("Server-side dry run passed.", out)

    def test_a_build_without_connector_images_fails(self):
        code, out = self.run_script(COMMIT, "staging", [])
        self.assertNotEqual(code, 0)
        self.assertIn("No registry-connector and registry-connector-ui image carries a build tag", out)


if __name__ == "__main__":
    unittest.main()
