"""Rollback of a failed New Dev deploy and the chart-pin updater, with stand-in helm/kubectl/GitHub.

No network, no cluster. Standard library only (runs on the Jenkins agent's stock Python).
    python3 -m unittest discover -s test -p test_deploy_ci.py -v
"""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

HELM = r'''#!/usr/bin/env bash
echo "helm $*" >> "$LOG"
case "$1" in
  template) echo "kind: ConfigMap" ;;
  get)      if [ -n "${NO_RELEASE:-}" ]; then echo "Error: release: not found" >&2; exit 1; fi; echo "registry: {}" ;;
  history)  case " $* " in *" json "*) echo "${HISTORY_JSON}" ;; *) echo "REVISION STATUS" ;; esac ;;
  upgrade)  exit "${UPGRADE_RC:-0}" ;;
  rollback) exit "${ROLLBACK_RC:-0}" ;;
esac
exit 0
'''

KUBECTL = r'''#!/usr/bin/env bash
echo "kubectl $*" >> "$LOG"
case "$1" in
  create) echo "{}" ;;
  rollout) case "$*" in *"${ROLLOUT_FAIL_ON:-NONE}"*) exit 1 ;; esac ;;
esac
exit 0
'''

# Stands in for ci/deploy/oan_chart.py (which would download the pinned chart).
CHART_STUB = r'''import os, sys
a = sys.argv[1:]
if a[0] == "fetch":
    os.makedirs(a[2], exist_ok=True)
    p = os.path.join(a[2], "chart.tgz"); open(p, "w").write("x"); print(p)
elif a[0] == "values":
    open(a[2], "w").write("registry: {}\n"); print(a[2])
elif a[0] == "version":
    print("1.0.0-dev.20")
'''

# The route guard (exit code GUARD_ROUTES_RC) and the Farmer-reference guard: it runs twice, before the
# upgrade on the render and after the rollouts on the live Deployments; GUARD_FAIL_ON=<n> fails the nth run.
ROUTES_STUB = "import os, sys\nsys.stdin.read()\nsys.exit(int(os.environ.get('GUARD_ROUTES_RC', '0')))\n"
GUARD_STUB = r'''import os, sys
sys.stdin.read()
n = 1
if os.path.exists("guard.count"):
    n = int(open("guard.count").read()) + 1
open("guard.count", "w").write(str(n))
sys.exit(1 if str(n) == os.environ.get("GUARD_FAIL_ON") else 0)
'''
DASHBOARD_STUB = '#!/usr/bin/env bash\nexit "${DASHBOARD_UI_RC:-0}"\n'

DEPLOYED = json.dumps([{"revision": 2, "status": "superseded"},
                       {"revision": 3, "status": "deployed", "chart": "openg2p-livestock-registry-1.0.0-dev.19"},
                       {"revision": 4, "status": "failed"}])

class DeployRollbackTests(unittest.TestCase):
    """ci/deploy/deploy-livestock-dev.sh: a failure from the upgrade onwards puts the release back."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        for rel in ("ci/deploy", "ci/refactor", "ci/dashboard"):
            (self.repo / rel).mkdir(parents=True)
        for name in ("deploy-livestock-dev.sh", "release-rollback.sh"):
            shutil.copy(ROOT / "ci/deploy" / name, self.repo / "ci/deploy" / name)
        shutil.copy(ROOT / "ci/deploy/bump_pin.py", self.repo / "ci/deploy/bump_pin.py")
        (self.repo / "ci/deploy/oan_chart.py").write_text(CHART_STUB)
        (self.repo / "ci/check-new-dev-routes.py").write_text(ROUTES_STUB)
        (self.repo / "ci/refactor/deployment_guard.py").write_text(GUARD_STUB)
        (self.repo / "ci/dashboard/deploy-ui.sh").write_text(DASHBOARD_STUB)
        self.bin = base / "bin"
        self.bin.mkdir()
        for name, body in (("helm", HELM), ("kubectl", KUBECTL)):
            path = self.bin / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        self.log = base / "calls.log"
        self.log.write_text("")

    def run_deploy(self, **env):
        e = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], LOG=str(self.log),
                 KUBECONFIG="/nonexistent", ECR_REGISTRY="123456789012.dkr.ecr.ap-south-1.amazonaws.com",
                 IMAGE_TAG="abcdef123456", BUILD_NUMBER="7", DASHBOARD_UI_ECR="oan/x", DASHBOARD_UI_SHA="deadbeefcafe",
                 HISTORY_JSON=DEPLOYED)
        e.update(env)
        out = base_out = Path(self.tmp.name) / "out.txt"
        with open(str(out), "w") as sink:       # a file, not a pipe: the log watcher's last `sleep` must not block us
            done = subprocess.run(["bash", str(self.repo / "ci/deploy/deploy-livestock-dev.sh")], cwd=str(self.repo),
                                  env=e, stdout=sink, stderr=subprocess.STDOUT, universal_newlines=True)
        return done.returncode, base_out.read_text(), self.log.read_text()

    def report(self):
        return (self.repo / "deploy-failure-7.txt").read_text()

    def test_success_does_not_roll_back(self):
        rc, out, calls = self.run_deploy()
        self.assertEqual(rc, 0, out)
        self.assertIn("rollback target: revision 3", out)
        self.assertNotIn("helm rollback", calls)
        self.assertIn("helm upgrade --install livestock-registry", calls)
        self.assertNotIn("--atomic", calls)
        self.assertFalse((self.repo / "deploy-failure-7.txt").exists())

    def test_failed_upgrade_rolls_back_to_last_deployed_revision(self):
        rc, out, calls = self.run_deploy(UPGRADE_RC="1")
        self.assertNotEqual(rc, 0)
        self.assertIn("helm rollback livestock-registry 3 -n livestock", calls)   # 3 = last `deployed`, not the failed 4
        self.assertIn("== failure: deploy failed", self.report())

    def test_failed_rollout_rolls_back(self):
        rc, out, calls = self.run_deploy(ROLLOUT_FAIL_ON="staff-portal-ui")
        self.assertNotEqual(rc, 0)
        self.assertIn("helm rollback livestock-registry 3 -n livestock", calls)

    def test_failed_dashboard_api_rollout_rolls_back(self):
        rc, out, calls = self.run_deploy(ROLLOUT_FAIL_ON="dashboard-api")
        self.assertNotEqual(rc, 0)
        self.assertIn("helm rollback livestock-registry 3 -n livestock", calls)

    def test_failed_dashboard_ui_deploy_rolls_back(self):
        rc, out, calls = self.run_deploy(DASHBOARD_UI_RC="1")
        self.assertNotEqual(rc, 0)
        self.assertIn("helm rollback livestock-registry 3 -n livestock", calls)

    def test_failed_guard_on_the_live_deployments_rolls_back(self):
        rc, out, calls = self.run_deploy(GUARD_FAIL_ON="2")
        self.assertNotEqual(rc, 0)
        self.assertIn("helm upgrade --install", calls)
        self.assertIn("helm rollback livestock-registry 3 -n livestock", calls)

    def test_diagnostics_are_saved_before_the_rollback(self):
        rc, out, calls = self.run_deploy(UPGRADE_RC="1")
        lines = calls.splitlines()
        rollback = next(i for i, l in enumerate(lines) if l.startswith("helm rollback"))
        events = max(i for i, l in enumerate(lines[:rollback]) if l.startswith("kubectl get events"))
        self.assertLess(events, rollback)

    def test_first_install_failure_has_nothing_to_roll_back_to(self):
        rc, out, calls = self.run_deploy(UPGRADE_RC="1", NO_RELEASE="1", HISTORY_JSON="[]")
        self.assertNotEqual(rc, 0)
        self.assertNotIn("helm rollback", calls)
        self.assertIn("no earlier deployed revision", out)

    def test_failure_without_a_deployed_revision_does_not_roll_back(self):
        rc, out, calls = self.run_deploy(UPGRADE_RC="1", HISTORY_JSON=json.dumps([{"revision": 1, "status": "failed"}]))
        self.assertNotEqual(rc, 0)
        self.assertNotIn("helm rollback", calls)

    def test_a_failed_rollback_still_fails_the_build(self):
        rc, out, calls = self.run_deploy(UPGRADE_RC="1", ROLLBACK_RC="1")
        self.assertNotEqual(rc, 0)
        self.assertIn("ROLLBACK FAILED", out)

    def test_failure_before_the_upgrade_changes_nothing_and_rolls_nothing_back(self):
        rc, out, calls = self.run_deploy(GUARD_ROUTES_RC="1")
        self.assertNotEqual(rc, 0)
        self.assertNotIn("helm upgrade", calls)
        self.assertNotIn("helm rollback", calls)

    def test_interrupted_release_is_refused_before_any_change(self):
        history = json.dumps([{"revision": 3, "status": "deployed"}, {"revision": 4, "status": "pending-upgrade"}])
        rc, out, calls = self.run_deploy(HISTORY_JSON=history)
        self.assertNotEqual(rc, 0)
        self.assertIn("pending Helm operation", out)
        self.assertNotIn("helm upgrade", calls)
        self.assertNotIn("helm rollback", calls)

    # ---- chart release mode: the develop build released its images in oan-helm and deploys that release

    def test_the_rollback_target_names_the_release_it_restores(self):
        rc, out, calls = self.run_deploy()
        self.assertIn("rollback target: revision 3 (openg2p-livestock-registry-1.0.0-dev.19, the last working release)", out)

    def test_the_build_images_are_set_on_the_pinned_chart(self):
        rc, out, calls = self.run_deploy()
        self.assertEqual(rc, 0, out)
        self.assertIn("registry.staffApi.image.tag=abcdef123456", calls)
        self.assertNotIn("helm rollback", calls)

    def test_the_upgrade_is_marked_started_only_just_before_helm_upgrade(self):
        text = (ROOT / "ci/deploy/deploy-livestock-dev.sh").read_text()
        self.assertLess(text.index("\nUPGRADE_STARTED=1"), text.index("if ! helm upgrade --install"))
        self.assertLess(text.index("helm template"), text.index("\nUPGRADE_STARTED=1"))
        self.assertNotIn("--atomic", text)


def load_bump():
    spec = importlib.util.spec_from_file_location("bump_pin_under_test", ROOT / "ci/deploy/bump_pin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_archive(version="1.0.0-dev.21", app="1.2.2-rc.700"):
    body = "apiVersion: v2\nname: openg2p-livestock-registry\nversion: %s\nappVersion: %s\n" % (version, app)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as archive:
        data = body.encode()
        info = tarfile.TarInfo("openg2p-livestock-registry/Chart.yaml")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class BumpPinTests(unittest.TestCase):
    COMMIT = "b" * 40

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bump = load_bump()
        profile = Path(self.tmp.name) / "oan-chart.json"
        shutil.copy(ROOT / "ci/deploy/oan-chart.json", profile)
        self.bump.PROFILE = profile
        self.archive = fake_archive()
        self.digest = hashlib.sha256(self.archive).hexdigest()
        self.files = {
            "releases/current.yaml": b"charts:\n  openg2p-livestock-registry: 1.0.0-dev.21\n  openg2p-farmer-registry: 1.0.0-dev.20\n",
            "repository/openg2p-livestock-registry-1.0.0-dev.21.tgz": self.archive,
            "repository/SHA256SUMS": ("%s  openg2p-livestock-registry-1.0.0-dev.21.tgz\n" % self.digest).encode(),
            "environments/dev/values/livestock.yaml": b"registry: {}\n",
        }

    def fetch(self, uri):
        path = uri.split("/oan-helm/" + self.COMMIT + "/")[1]
        return self.files[path]

    def test_pin_is_rebuilt_from_the_commit(self):
        profiles = self.bump.new_pin(self.COMMIT, fetch=self.fetch)
        pin = profiles["registry"]
        self.assertEqual(pin["version"], "1.0.0-dev.21")          # taken from releases/current.yaml
        self.assertEqual(pin["sha256"], self.digest)
        self.assertEqual(pin["platformVersion"], "1.2.2-rc.700")  # read from the archive
        self.assertTrue(pin["repository"].endswith("/oan-helm/" + self.COMMIT + "/repository/"))
        self.assertEqual(pin["values"]["url"], pin["repository"][:-len("repository/")] + pin["values"]["path"])
        self.assertEqual(pin["values"]["sha256"], hashlib.sha256(b"registry: {}\n").hexdigest())
        self.assertEqual(pin["namespace"], "livestock")           # untouched fields stay
        self.assertIs(pin["promotionReady"], True)
        self.assertEqual(profiles["dashboard"], json.loads((ROOT / "ci/deploy/oan-chart.json").read_text())["dashboard"])

    def test_archive_not_matching_sha256sums_is_rejected(self):
        self.files["repository/SHA256SUMS"] = ("%s  openg2p-livestock-registry-1.0.0-dev.21.tgz\n" % ("0" * 64)).encode()
        with self.assertRaisesRegex(ValueError, "SHA256SUMS"):
            self.bump.new_pin(self.COMMIT, fetch=self.fetch)

    def test_version_missing_from_sha256sums_is_rejected(self):
        self.files["repository/SHA256SUMS"] = b""
        with self.assertRaisesRegex(ValueError, "not listed"):
            self.bump.new_pin(self.COMMIT, fetch=self.fetch)

    def test_archive_with_another_chart_version_is_rejected(self):
        self.files["repository/openg2p-livestock-registry-1.0.0-dev.21.tgz"] = fake_archive(version="1.0.0-dev.20")
        self.files["repository/SHA256SUMS"] = ("%s  openg2p-livestock-registry-1.0.0-dev.21.tgz\n" % hashlib.sha256(
            self.files["repository/openg2p-livestock-registry-1.0.0-dev.21.tgz"]).hexdigest()).encode()
        with self.assertRaisesRegex(ValueError, "expected 1.0.0-dev.21"):
            self.bump.new_pin(self.COMMIT, fetch=self.fetch)

    def test_branch_or_short_commit_is_rejected(self):
        for bad in ("main", "abc1234", "B" * 40):
            with self.assertRaises(ValueError):
                self.bump.new_pin(bad, fetch=self.fetch)

    def test_placeholder_version_is_rejected(self):
        with self.assertRaises(ValueError):
            self.bump.new_pin(self.COMMIT, version="0.0.0-develop.1", fetch=self.fetch)


class ProposePinTests(unittest.TestCase):
    """--latest: what the scheduled workflow uses to decide whether to open a pin pull request."""
    HEAD = "c" * 40

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bump = load_bump()
        self.root = Path(self.tmp.name)
        (self.root / "ci/deploy").mkdir(parents=True)
        shutil.copy(ROOT / "ci/deploy/oan-chart.json", self.root / "ci/deploy/oan-chart.json")
        self.bump.PROFILE = self.root / "ci/deploy/oan-chart.json"
        self.bump.ROOT = self.root
        self.old = json.loads(self.bump.PROFILE.read_text(encoding="utf-8"))
        self.pinned = self.old["registry"]
        self.files = {}

    def publish(self, version, app, values=b"registry: {}\n"):
        archive = fake_archive(version=version, app=app)
        name = "openg2p-livestock-registry-%s.tgz" % version
        self.files = {
            "releases/current.yaml": ("charts:\n  openg2p-livestock-registry: %s\n" % version).encode(),
            "repository/" + name: archive,
            "repository/SHA256SUMS": ("%s  %s\n" % (hashlib.sha256(archive).hexdigest(), name)).encode(),
            "environments/dev/values/livestock.yaml": values,
        }
        return hashlib.sha256(archive).hexdigest()

    def fetch(self, uri):
        return self.files[uri.split("/oan-helm/" + self.HEAD + "/")[1]]

    def propose(self):
        return self.bump.proposal(self.old, fetch=self.fetch, head=lambda: self.HEAD)

    def test_version_order(self):
        key = self.bump.version_key
        self.assertLess(key("1.0.0-dev.9"), key("1.0.0-dev.10"))     # numeric, not text order
        self.assertLess(key("1.0.0-dev.20"), key("1.0.0-dev.21"))
        self.assertLess(key("1.0.0-dev.99"), key("1.0.0"))
        with self.assertRaises(ValueError):
            key("latest")

    def test_newer_chart_is_proposed(self):
        self.publish("1.0.0-dev.21", self.pinned["platformVersion"])
        new, why = self.propose()
        self.assertIsNotNone(new)
        self.assertIn("newer chart 1.0.0-dev.21", why)
        self.assertTrue(new["registry"]["repository"].endswith("/oan-helm/" + self.HEAD + "/repository/"))

    def test_same_chart_and_values_is_up_to_date(self):
        digest = self.publish(self.pinned["version"], self.pinned["platformVersion"])
        self.pinned["sha256"] = digest                      # as if the archive were the pinned one
        self.pinned["values"]["sha256"] = hashlib.sha256(self.files["environments/dev/values/livestock.yaml"]).hexdigest()
        new, why = self.propose()
        self.assertIsNone(new)
        self.assertIn("up to date", why)

    def test_values_only_change_is_proposed_with_the_same_chart(self):
        digest = self.publish(self.pinned["version"], self.pinned["platformVersion"], values=b"registry: {changed: true}\n")
        self.pinned["sha256"] = digest
        new, why = self.propose()
        self.assertIsNotNone(new)
        self.assertIn("public values changed", why)
        self.assertEqual(new["registry"]["version"], self.pinned["version"])

    def test_older_chart_is_never_proposed(self):
        self.publish("1.0.0-dev.18", "1.2.2-rc.600")
        with self.assertRaisesRegex(ValueError, "downgrade"):
            self.propose()

    def test_changed_archive_for_the_same_version_is_refused(self):
        self.publish(self.pinned["version"], "1.2.2-rc.999")  # different bytes, same version
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.propose()

    def test_head_commit_is_read_with_git_ls_remote(self):
        out = "%s\trefs/heads/main\n" % self.HEAD
        self.assertEqual(self.bump.head_commit(run=lambda cmd: out), self.HEAD)
        with self.assertRaises(ValueError):
            self.bump.head_commit(run=lambda cmd: "")

    def test_only_the_pin_is_rewritten_even_for_a_new_platform(self):
        self.publish("1.0.0-dev.21", "1.2.2-rc.700")
        new, _ = self.propose()
        self.assertEqual(new["registry"]["platformVersion"], "1.2.2-rc.700")
        self.assertEqual(self.bump.update_companions(self.pinned, new["registry"], root=self.root), [])
        self.assertEqual(self.bump.apply_pin(self.old, new, self.root), ["ci/deploy/oan-chart.json"])
        written = json.loads((self.root / "ci/deploy/oan-chart.json").read_text())
        self.assertEqual(written["registry"]["version"], "1.0.0-dev.21")
        self.assertEqual(written["dashboard"], self.old["dashboard"])      # the dashboard pin is never touched


def load_propose():
    spec = importlib.util.spec_from_file_location("propose_under_test", ROOT / "ci/deploy/propose_pin_pr.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProposePullRequestTests(unittest.TestCase):
    """The last Jenkins stage: opens the pin pull request, with a stand-in git and GitHub."""
    TOKEN = "tok-SECRET-123"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "ci/deploy").mkdir(parents=True)
        shutil.copy(ROOT / "ci/deploy/oan-chart.json", self.root / "ci/deploy/oan-chart.json")
        self.mod = load_propose()
        self.bump = load_bump()
        self.bump.PROFILE = self.root / "ci/deploy/oan-chart.json"
        self.bump.ROOT = self.root
        old = json.loads(self.bump.PROFILE.read_text(encoding="utf-8"))
        new = json.loads(json.dumps(old))
        pin = new["registry"]
        pin["version"] = "1.0.0-dev.21"
        pin["sha256"] = "a" * 64
        pin["values"]["sha256"] = "b" * 64
        pin["repository"] = "https://raw.githubusercontent.com/Centre-for-Open-Societal-Systems/oan-helm/" + "e" * 40 + "/repository/"
        pin["values"]["url"] = pin["repository"][:-len("repository/")] + pin["values"]["path"]
        self.new = new
        self.proposal_result = (new, "newer chart 1.0.0-dev.21 released (pinned 1.0.0-dev.19)")
        self.bump.proposal = lambda old_profile: self.proposal_result
        self.cmds = []
        self.calls = []
        self.exists = ""          # what `git ls-remote` prints
        self.pulls = (200, [])    # answer to the pull request list
        self.create = (201, {"html_url": "https://github.com/o/r/pull/7"})
        self.fail_on = None       # a label whose command should fail

    def runner(self, cmd, label=None, cwd=None, env=None, check=True):
        self.cmds.append((label or cmd[0], cmd))
        if label == self.fail_on:
            raise RuntimeError("%s failed (exit 1):\nboom" % label)
        if label == "git remote get-url":
            return "https://github.com/o/r.git\n"
        if label == "git rev-parse":
            return "f" * 40 + "\n"
        if label == "git ls-remote":
            return self.exists
        return ""

    def call(self, method, path, token, payload=None):
        self.calls.append((method, path, payload))
        return self.pulls if method == "GET" else self.create

    def go(self, token=None):
        out = io.StringIO()
        import contextlib
        with contextlib.redirect_stdout(out):
            code = self.mod.propose(self.TOKEN if token is None else token, bump=self.bump, runner=self.runner,
                                    call=self.call, root=self.root)
        return code, out.getvalue()

    def labels(self):
        return [label for label, _ in self.cmds]

    def test_nothing_to_do_touches_neither_git_nor_github(self):
        self.proposal_result = (None, "up to date: chart 1.0.0-dev.19 and its values are unchanged on oan-helm main")
        code, out = self.go()
        self.assertEqual((code, self.cmds, self.calls), (0, [], []))
        self.assertIn("up to date", out)

    def test_a_needed_update_without_a_credential_proposes_nothing(self):
        code, out = self.go(token="")
        self.assertEqual(code, 3)
        self.assertEqual((self.cmds, self.calls), ([], []))
        self.assertIn("no GitHub credential", out)

    def test_a_new_platform_version_is_reported_and_not_proposed(self):
        self.new["registry"]["platformVersion"] = "1.2.2-rc.700"
        code, out = self.go()
        self.assertEqual(code, 5)
        self.assertEqual((self.cmds, self.calls), ([], []))
        self.assertIn("scripts/bump-rp-version.sh", out)

    def test_full_proposal_flow(self):
        code, out = self.go()
        self.assertEqual(code, 0, out)
        labels = self.labels()
        order = ["git rev-parse", "the pin tests", "verified prefetch of the new pin", "git checkout -b", "git add",
                 "git commit", "git push", "git checkout", "git branch -D"]
        positions = [labels.index(name) for name in order]
        self.assertEqual(positions, sorted(positions))
        # the pin and the files that must agree with it were rewritten on disk
        self.assertIn("1.0.0-dev.21", (self.root / "ci/deploy/oan-chart.json").read_text())
        add = next(cmd for label, cmd in self.cmds if label == "git add")
        self.assertEqual(add[-1], "ci/deploy/oan-chart.json")
        self.assertEqual(add[-2:], ["--", "ci/deploy/oan-chart.json"])
        # the pull request goes to develop from a branch named for the version and values
        method, path, payload = self.calls[-1]
        self.assertEqual((method, path), ("POST", "/repos/o/r/pulls"))
        self.assertEqual(payload["base"], "develop")
        self.assertEqual(payload["head"], "bot/oan-chart-pin-1.0.0-dev.21-" + "b" * 8)
        self.assertIn("Merging this deploys to New Dev", payload["body"])
        self.assertIn("opened https://github.com/o/r/pull/7", out)
        # the workspace is restored to the commit the build checked out
        restore = next(cmd for label, cmd in self.cmds if label == "git checkout")
        self.assertEqual(restore[-1], "f" * 40)

    def test_the_token_is_never_printed_or_used_as_a_label(self):
        code, out = self.go()
        self.assertNotIn(self.TOKEN, out)
        self.assertNotIn(self.TOKEN, " ".join(self.labels()))
        push = next(cmd for label, cmd in self.cmds if label == "git push")
        self.assertNotIn(self.TOKEN, " ".join(push))                  # sent only as a base64 basic-auth header
        self.assertTrue(any(a.startswith("http.extraheader=AUTHORIZATION: basic ") for a in push))

    def test_an_existing_pull_request_is_not_proposed_again(self):
        self.pulls = (200, [{"html_url": "https://github.com/o/r/pull/3", "state": "closed"}])
        code, out = self.go()
        self.assertEqual(code, 0)
        self.assertIn("Already proposed", out)
        self.assertNotIn("git push", self.labels())
        self.assertEqual([c[0] for c in self.calls], ["GET"])

    def test_an_existing_branch_without_a_pull_request_only_opens_the_pull_request(self):
        self.exists = "abc\trefs/heads/bot/x\n"
        code, out = self.go()
        self.assertEqual(code, 0)
        self.assertNotIn("git push", self.labels())
        self.assertEqual(self.calls[-1][0], "POST")

    def test_failed_verification_pushes_nothing_and_restores_the_workspace(self):
        self.fail_on = "the pin tests"
        with self.assertRaisesRegex(RuntimeError, "the pin tests failed"):
            self.go()
        self.assertNotIn("git push", self.labels())
        self.assertIn("git checkout", self.labels())
        self.assertEqual([c[0] for c in self.calls], ["GET"])

    def test_github_refusing_to_list_pull_requests_is_reported(self):
        self.pulls = (403, {"message": "Resource not accessible by integration"})
        code, out = self.go()
        self.assertEqual(code, 4)
        self.assertIn("Pull requests write", out)
        self.assertNotIn("git push", self.labels())

    def test_github_refusing_to_create_the_pull_request_is_reported(self):
        self.create = (403, {"message": "Resource not accessible by integration"})
        code, out = self.go()
        self.assertEqual(code, 4)
        self.assertIn("is pushed; open the pull request", out)

    def test_repository_slug(self):
        slug = self.mod.slug_of
        self.assertEqual(slug("https://github.com/Centre-for-Open-Societal-Systems/livestock-registry.git\n"),
                         "Centre-for-Open-Societal-Systems/livestock-registry")
        self.assertEqual(slug("git@github.com:o/r.git"), "o/r")
        with self.assertRaises(ValueError):
            slug("https://gitlab.com/o/r.git")



# ---- the images go into the oan-helm chart ----------------------------------------------------------------------

def load_release():
    spec = importlib.util.spec_from_file_location("release_images_under_test", ROOT / "ci/deploy/release_images.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REG = "123456789012.dkr.ecr.ap-south-1.amazonaws.com"
PATH_ = "openg2p/livestock-registry"
OLD_TAG = "bf78e69a5fd6"


def sample_values(tag=OLD_TAG, digests=None):
    """The shape of charts/openg2p-livestock-registry/values.yaml in oan-helm, reduced."""
    digests = digests or {}

    def img(component, section_digest):
        return ("    image:\n      repository: %s/%s/%s\n      tag: %s@sha256:%s\n" % (REG, PATH_, component, tag, section_digest))
    old = "e" * 64
    return (
        "global:\n  baseDomain: development.oanstaging.com\n"
        "registry:\n"
        "  keycloak-init:\n    image:\n      repository: docker.io/x/y\n      tag: 1.0.0\n"
        "  staffApi:\n" + img("staff-api", old) + "    envVars:\n      A: 'b'\n"
        "# a comment at column 0 inside the registry block\n"
        "  partnerApi:\n" + img("partner-api", old) +
        "  celeryWorker:\n" + img("celery", old) +
        "  celeryBeat:\n" + img("celery", old) +
        "  dbSeed:\n" + img("db-seed", old) + "    loadGeoData: false\n"
        "  staffUi:\n" + img("staff-ui", old) +
        "  sanity:\n    enabled: true\n" + img("sanity-tests", old) + "    regType: Livestock\n"
        "reporting:\n  image:\n    repository: ''\n    tag: ''\n"
        "dashboardApi:\n  enabled: false\n  image:\n    digest: sha256:%s\n    repository: %s/%s/dashboard-api\n    tag: %s\n  replicas: 1\n"
        "dashboardUi:\n  image:\n    repository: ''\n    tag: ''\n" % (old, REG, PATH_, tag))


NEW_TAG = "0123456789ab"


def release_digests():
    return dict((c, "sha256:" + ("%x" % (i + 1)) * 64) for i, c in enumerate(
        ["staff-api", "partner-api", "celery", "db-seed", "sanity-tests", "staff-ui", "dashboard-api"]))


class ImageValuesTests(unittest.TestCase):
    def setUp(self):
        self.r = load_release()
        self.tags, self.dash = self.r.wanted(NEW_TAG, release_digests())
        self.repos = self.r.expected_repositories(REG, PATH_)

    def test_only_the_image_lines_change(self):
        old = sample_values()
        new = self.r.rewrite_values(old, self.tags, self.dash, self.repos)
        changed = [(a, b) for a, b in zip(old.split("\n"), new.split("\n")) if a != b]
        self.assertEqual(len(old.split("\n")), len(new.split("\n")))
        self.assertEqual(len(changed), 9)                          # seven registry tags + dashboard digest and tag
        self.assertTrue(all(b.lstrip().startswith(("tag:", "digest:")) for _, b in changed))
        self.assertIn("      tag: %s@%s" % (NEW_TAG, release_digests()["staff-api"]), new)
        self.assertIn("    tag: '%s'\n" % NEW_TAG, new)
        self.assertIn("    digest: %s\n" % release_digests()["dashboard-api"], new)
        # untouched: the comment, other images, the empty reporting and dashboardUi images
        for kept in ("# a comment at column 0 inside the registry block", "tag: 1.0.0", "    tag: ''", "      A: 'b'"):
            self.assertIn(kept, new)

    def test_an_all_digit_commit_tag_stays_a_string_in_the_values(self):
        # Build 875427410733 made --set render image:%!s(int64=...); the same trap exists in the values file.
        try:
            import yaml
        except ModuleNotFoundError:
            sys.path.append(str(ROOT / "ci/deploy/vendor"))     # the deploy node's pure-Python PyYAML
            import yaml
        for tag in ("875427410733", "123456e78901", "000000000001"):
            tags, dash = self.r.wanted(tag, release_digests())
            new = self.r.rewrite_values(sample_values(), tags, dash, self.repos)
            document = yaml.safe_load(new)
            self.assertEqual(document["dashboardApi"]["image"]["tag"], tag)
            self.assertIsInstance(document["dashboardApi"]["image"]["tag"], str)
            self.assertIsInstance(document["registry"]["staffApi"]["image"]["tag"], str)
            self.assertTrue(self.r.carries(new, tags, dash))

    def test_both_celery_workloads_get_the_celery_digest(self):
        new = self.r.rewrite_values(sample_values(), self.tags, self.dash, self.repos)
        self.assertEqual(new.count("%s@%s" % (NEW_TAG, release_digests()["celery"])), 2)

    def test_rewriting_twice_changes_nothing_and_carries_says_so(self):
        once = self.r.rewrite_values(sample_values(), self.tags, self.dash, self.repos)
        self.assertEqual(self.r.rewrite_values(once, self.tags, self.dash, self.repos), once)
        self.assertTrue(self.r.carries(once, self.tags, self.dash))
        self.assertFalse(self.r.carries(sample_values(), self.tags, self.dash))

    def test_another_ecr_repository_is_refused(self):
        bad = sample_values().replace("/staff-api", "/someone-elses-api")
        with self.assertRaisesRegex(ValueError, "staffApi image repository"):
            self.r.rewrite_values(bad, self.tags, self.dash, self.repos)

    def test_a_missing_section_is_an_error_not_a_silent_skip(self):
        with self.assertRaises(ValueError):
            self.r.rewrite_values(sample_values().replace("  dbSeed:", "  dbSeedX:"), self.tags, self.dash, self.repos)

    def test_digests_are_read_and_validated(self):
        text = "".join("%s\t%s\n" % kv for kv in release_digests().items())
        self.assertEqual(self.r.read_digests(text), release_digests())
        for bad in ("staff-api\tlatest\n", "staff-api sha256:" + "a" * 64 + "\n"):
            with self.assertRaises(ValueError):
                self.r.read_digests(bad)

    def test_every_component_needs_a_digest_and_the_tag_a_commit(self):
        partial = dict(release_digests())
        del partial["sanity-tests"]
        with self.assertRaisesRegex(ValueError, "sanity-tests"):
            self.r.wanted(NEW_TAG, partial)
        with self.assertRaises(ValueError):
            self.r.wanted("latest", release_digests())

    def test_images_are_read_back_from_the_values(self):
        written = self.r.rewrite_values(sample_values(), self.tags, self.dash, self.repos)
        tags, dashboard = self.r.read_images(written)
        self.assertEqual((tags, dashboard), (self.tags, self.dash))
        self.assertEqual(self.r.rewrite_values(written, tags, dashboard, self.repos), written)
        unpinned = written.replace("tag: %s@%s" % (NEW_TAG, release_digests()["staff-ui"]), "tag: latest", 1)
        with self.assertRaisesRegex(ValueError, "staffUi"):
            self.r.read_images(unpinned)

    def test_the_archive_values_are_read_for_the_release_check(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as archive:
            data = sample_values().encode()
            info = tarfile.TarInfo("openg2p-livestock-registry/values.yaml")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        self.assertEqual(self.r.archive_values(buf.getvalue()), sample_values())


FORK = "fork-owner/oan-helm"


class FakeGitHub(object):
    """oan-helm as pipeline 1 sees it: the org repo (main, pull requests) and the fork (branch, commit)."""

    def __init__(self, release):
        self.r = release
        self.main_sha = "a" * 40
        self.text = sample_values()                 # values.yaml on the org repo's main
        self.branches = {}                          # fork branch -> text
        self.knows_commit = True                    # False: the fork cannot see main's head until it is synced
        self.pulls = []                             # open pull requests on the org repo
        self.calls = []
        self.refuse = {}                            # (method, path-prefix) -> status
        self.synced = False

    def __call__(self, method, path, token, payload=None):
        self.calls.append((method, path, payload))
        for (m, prefix), status in self.refuse.items():
            if method == m and prefix in path:
                return status, {"message": "refused"}
        org, fork = "/repos/%s" % self.r.SLUG, "/repos/%s" % FORK
        if path.startswith(org):
            rest = path[len(org):]
            if method == "GET" and rest == "/git/ref/heads/main":
                return 200, {"object": {"sha": self.main_sha}}
            if method == "GET" and rest.startswith("/contents/") and rest.endswith("?ref=main"):
                return 200, {"content": base64.b64encode(self.text.encode()).decode(), "sha": "blob1"}
            if method == "GET" and rest.startswith("/pulls?"):
                return 200, list(self.pulls)
            if method == "POST" and rest == "/pulls":
                pull = {"number": 11, "html_url": "https://github.com/%s/pull/11" % self.r.SLUG, "payload": payload}
                self.pulls.append(pull)
                return 201, pull
            if method == "PATCH" and rest.startswith("/pulls/"):
                self.pulls[0]["payload"] = payload
                return 200, {}
        elif path.startswith(fork):
            rest = path[len(fork):]
            if method == "POST" and rest == "/merge-upstream":
                self.synced = self.knows_commit = True
                return 200, {}
            if method == "POST" and rest == "/git/refs":
                name = payload["ref"][len("refs/heads/"):]
                if name in self.branches:
                    return 422, {"message": "Reference already exists"}
                if not self.knows_commit:
                    return 422, {"message": "Object does not exist"}
                self.branches[name] = self.text
                return 201, {}
            if method == "PATCH" and rest.startswith("/git/refs/heads/"):
                self.branches[rest[len("/git/refs/heads/"):]] = self.text
                return 200, {}
            if method == "GET" and rest.startswith("/contents/"):
                return 200, {"content": base64.b64encode(self.branches[rest.split("?ref=")[1]].encode()).decode(), "sha": "blob1"}
            if method == "PUT" and rest.startswith("/contents/"):
                self.branches[payload["branch"]] = base64.b64decode(payload["content"]).decode()
                return 200, {}
        raise AssertionError("unexpected call %s %s" % (method, path))


class ImagePullRequestTests(unittest.TestCase):
    """Pipeline 1: ci/deploy/release_images.py opens the pull request and stops."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".build").mkdir()
        (self.root / ".build/image-digests.tsv").write_text("".join("%s\t%s\n" % kv for kv in release_digests().items()))
        self.r = load_release()
        self.gh = FakeGitHub(self.r)
        self.out = []
        self.env = {"IMAGE_TAG": NEW_TAG, "ECR_REGISTRY": REG, "ECR_PATH": PATH_, "COMMIT_SUBJECT": "Add a field",
                    "SOURCE_COMMIT": NEW_TAG + "f" * 28, "BUILD_URL": "https://jenkins/job/7/"}
        self.tags, self.dash = self.r.wanted(NEW_TAG, release_digests())

    def proposal(self):
        return self.r.Proposal("tok", "fork-owner", "oan-helm", call=self.gh, out=self.out.append)

    def run_stage(self, **overrides):
        env = dict(self.env, **overrides)
        return self.proposal().run(env, self.root, (self.root / ".build/image-digests.tsv").read_text())

    def methods(self):
        return [(m, p.split("?")[0].replace("/repos/%s" % self.r.SLUG, "ORG").replace("/repos/%s" % FORK, "FORK"))
                for m, p, _ in self.gh.calls]

    def test_the_branch_goes_to_the_fork_and_the_pull_request_to_the_org_main(self):
        url = self.run_stage()
        self.assertEqual(url, "https://github.com/%s/pull/11" % self.r.SLUG)
        calls = self.methods()
        order = [("POST", "FORK/git/refs"), ("PUT", "FORK/contents/charts/openg2p-livestock-registry/values.yaml"),
                 ("POST", "ORG/pulls")]
        positions = [calls.index(c) for c in order]
        self.assertEqual(positions, sorted(positions))
        branch = "bot/livestock-images-" + NEW_TAG
        self.assertIn("%s@%s" % (NEW_TAG, release_digests()["staff-api"]), self.gh.branches[branch])
        _, _, body = next(c for c in self.gh.calls if c[0] == "POST" and c[1].endswith("/pulls"))
        self.assertEqual((body["base"], body["head"]), ("main", "fork-owner:" + branch))
        self.assertIn("Livestock registry images %s: Add a field" % NEW_TAG, body["title"])
        self.assertIn("https://jenkins/job/7/", body["body"])
        # nothing in the org repo is written, merged or waited for
        self.assertEqual([m for m, p in calls if p.startswith("ORG") and m not in ("GET", "POST")], [])
        self.assertFalse([c for c in calls if "merge" in c[1] or "check-runs" in c[1]])

    def test_only_the_image_lines_of_the_chart_are_changed_on_the_branch(self):
        self.run_stage()
        old = sample_values().split("\n")
        new = self.gh.branches["bot/livestock-images-" + NEW_TAG].split("\n")
        changed = [b for a, b in zip(old, new) if a != b]
        self.assertEqual(len(old), len(new))
        self.assertEqual(len(changed), 9)
        self.assertTrue(all(c.lstrip().startswith(("tag:", "digest:")) for c in changed))

    def test_a_commit_that_oan_helm_main_already_carries_opens_nothing(self):
        self.gh.text = self.r.rewrite_values(sample_values(), self.tags, self.dash)
        self.assertIsNone(self.run_stage())
        calls = self.methods()
        self.assertNotIn(("POST", "ORG/pulls"), calls)
        self.assertNotIn(("POST", "FORK/git/refs"), calls)
        self.assertIn("already in oan-helm main", self.proposal_note())

    def proposal_note(self):
        p = self.proposal()
        p.run(dict(self.env), self.root, (self.root / ".build/image-digests.tsv").read_text())
        return p.note

    def test_a_rebuild_with_new_digests_for_the_same_commit_is_still_skipped(self):
        other = dict(release_digests(), **{"staff-api": "sha256:" + "9" * 64})
        self.gh.text = self.r.rewrite_values(sample_values(), *self.r.wanted(NEW_TAG, other))
        self.assertIsNone(self.run_stage())
        self.assertNotIn(("POST", "ORG/pulls"), self.methods())

    def test_a_left_over_branch_is_reset_and_the_open_pull_request_is_updated_not_duplicated(self):
        self.gh.branches["bot/livestock-images-" + NEW_TAG] = "stale"
        self.gh.pulls.append({"number": 5, "html_url": "https://github.com/%s/pull/5" % self.r.SLUG, "payload": {}})
        url = self.run_stage()
        self.assertEqual(url, "https://github.com/%s/pull/5" % self.r.SLUG)
        calls = self.methods()
        self.assertIn(("PATCH", "FORK/git/refs/heads/bot/livestock-images-" + NEW_TAG), calls)
        self.assertIn(("PATCH", "ORG/pulls/5"), calls)
        self.assertNotIn(("POST", "ORG/pulls"), calls)
        self.assertIn(NEW_TAG, self.gh.branches["bot/livestock-images-" + NEW_TAG])

    def test_a_fork_that_has_not_seen_main_yet_is_synced_first(self):
        self.gh.knows_commit = False
        self.run_stage()
        self.assertTrue(self.gh.synced)
        self.assertIn(("POST", "ORG/pulls"), self.methods())
        self.assertIn("syncing", "\n".join(self.out))

    def test_a_fork_that_cannot_be_synced_is_reported(self):
        self.gh.knows_commit = False
        self.gh.refuse[("POST", "/merge-upstream")] = 409
        with self.assertRaises(self.r.Stop) as caught:
            self.run_stage()
        self.assertEqual(caught.exception.code, 4)
        self.assertIn("Sync fork", str(caught.exception))

    def test_a_token_without_access_is_reported_as_such(self):
        self.gh.refuse[("POST", "/git/refs")] = 403
        with self.assertRaises(self.r.Stop) as caught:
            self.run_stage()
        self.assertEqual(caught.exception.code, 4)
        self.assertIn("public_repo", str(caught.exception))
        self.assertNotIn("tok", str(caught.exception).replace("token", ""))

    def test_refused_pull_request_is_reported(self):
        self.gh.refuse[("POST", "/pulls")] = 403
        with self.assertRaises(self.r.Stop) as caught:
            self.run_stage()
        self.assertEqual(caught.exception.code, 4)

    def test_dry_run_changes_nothing(self):
        self.assertIsNone(self.run_stage(DRY_RUN="1"))
        self.assertEqual([m for m, _ in self.methods() if m != "GET"], [])

    def test_main_writes_the_pull_request_url_and_nothing_else(self):
        import contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.r.main(env=dict(self.env, GH_TOKEN="tok", GH_USER="fork-owner"), root=self.root, call=self.gh)
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual((self.root / ".build/oan-helm-pr.txt").read_text().strip(), "https://github.com/%s/pull/11" % self.r.SLUG)
        self.assertNotIn("tok", out.getvalue().replace("token", ""))

    def test_main_without_a_credential_is_exit_3_and_opens_nothing(self):
        import contextlib
        for env in (dict(self.env), dict(self.env, GH_TOKEN="tok"), dict(self.env, GH_USER="fork-owner")):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.r.main(env=env, root=self.root, call=self.gh)
            self.assertEqual(code, 3)
        self.assertEqual(self.gh.calls, [])
        self.assertFalse((self.root / ".build/oan-helm-pr.txt").exists())

    def test_main_leaves_no_pull_request_file_when_the_commit_was_already_taken(self):
        import contextlib
        self.gh.text = self.r.rewrite_values(sample_values(), self.tags, self.dash)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.r.main(env=dict(self.env, GH_TOKEN="tok", GH_USER="fork-owner"), root=self.root, call=self.gh)
        self.assertEqual(code, 0)
        self.assertFalse((self.root / ".build/oan-helm-pr.txt").exists())


class PipelineWiringTests(unittest.TestCase):
    """ci/pipelines/dev.groovy: one pipeline, images -> deploy (with rollback) -> oan-helm pull request."""

    def setUp(self):
        self.text = (ROOT / "ci/pipelines/dev.groovy").read_text()

    def stage(self, name, following):
        return self.text.split("stage('%s')" % name, 1)[1].split("stage('%s')" % following, 1)[0]

    def test_stages_run_in_the_order_images_deploy_pull_request_pin(self):
        order = [self.text.index("stage('%s')" % n) for n in
                 ("Build & Push Images", "Deploy to Development", "Open oan-helm image PR", "Propose chart pin update")]
        self.assertEqual(order, sorted(order))

    def test_there_is_one_pipeline_file_for_the_normal_flow(self):
        self.assertFalse((ROOT / "ci/pipelines/deploy-newdev.groovy").exists())
        self.assertFalse((ROOT / "ci/deploy/latest_release.py").exists())

    def test_the_deploy_stage_still_fails_the_build_and_uses_the_pinned_chart_with_this_builds_images(self):
        stage = self.stage("Deploy to Development", "Upgrade connector (New Dev)")
        self.assertIn("bash ci/deploy/deploy-livestock-dev.sh", stage)
        self.assertIn("IMAGE_TAG=${env.IMAGE_TAG}", stage)
        self.assertNotIn("catchError(", stage)                              # a failed deploy fails the build
        for gone in ("OAN_CHART_PIN_FILE", "candidate", "NEWDEV_SKIP_DEPLOY"):
            self.assertNotIn(gone, self.text)

    def test_digests_are_captured_after_the_pushes_and_stashed(self):
        build = self.stage("Build & Push Images", "Stash deploy")
        self.assertIn("aws ecr describe-images", build)
        self.assertIn("stash name: 'image-digests'", build)
        self.assertLess(build.index("docker push ${api}"), build.index("describe-images"))

    def test_the_pull_request_stage_follows_the_deploy_and_cannot_fail_the_build(self):
        stage = self.stage("Open oan-helm image PR", "Propose chart pin update")
        self.assertIn("catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE')", stage)
        self.assertIn("python3 ci/deploy/release_images.py", stage)
        self.assertIn("agent { label 'vpn-agent2' }", stage)
        self.assertIn("branch 'develop'", stage)
        self.assertIn("unstash 'image-digests'", stage)
        self.assertIn("OAN_HELM_FORK_CRED_ID", stage)
        self.assertIn("rm -f .build/oan-helm-pr.txt", stage)
        for absent in ("KUBECONFIG", "helm upgrade", "stash name"):
            self.assertNotIn(absent, stage)
        self.assertIn("OAN_HELM_FORK_CRED_ID    = 'oan-helm-fork-token'", self.text)
        # no maintenance run opens an image pull request
        self.assertIn("['fresh-install', 'connector-plan', 'connector-upgrade']", stage)

    def test_the_pin_stage_is_the_one_that_was_already_there(self):
        stage = self.text.split("stage('Propose chart pin update')", 1)[1].split("stage('Deploy to Live')", 1)[0]
        self.assertIn("python3 ci/deploy/propose_pin_pr.py", stage)
        self.assertNotIn("OAN_CHART_PIN_FILE", stage)

    def test_braces_balance(self):
        self.assertEqual(self.text.count("{"), self.text.count("}"))


if __name__ == "__main__":
    unittest.main()
