"""After a successful deploy: put this build's images into the oan-helm Livestock chart through a pull request.

Run by the stage "Open oan-helm image PR" of every develop build, after the images were pushed to ECR and deployed to New Dev
(with a rollback if that failed, in which case this stage does not run). It does not wait for the pull request to be merged:
the stage, and the build, are a success once the pull request is open.

  1. Read the ECR digests of the build (.build/image-digests.tsv: component<TAB>sha256:...).
  2. Rewrite the image tags in charts/openg2p-livestock-registry/values.yaml of oan-helm to
     <commit12>@sha256:<digest> (staffApi, partnerApi, celeryWorker, celeryBeat, dbSeed, staffUi, sanity) and the
     tag and digest of dashboardApi. Only those lines change; the file is edited as text.
  3. Put that change on the branch bot/livestock-images-<commit12> of the FORK of oan-helm (GH_USER/oan-helm), created from
     the current head of the org repo's main, and open a pull request from it into
     Centre-for-Open-Societal-Systems/oan-helm main (or update the open one for the same commit).

A person with write access reviews and merges that pull request. oan-helm's release workflow then publishes the next
chart version and writes the CHANGELOG entry. Nothing here touches the cluster; the chart pin of this repository
moves in the separate "Propose chart pin update" stage.

A commit whose images oan-helm main already carries is left alone (a re-run, Replay or rebuild would only give new digests
for the same tag): one pull request per commit merged to develop.

Needs GH_USER (the account that owns the fork) and GH_TOKEN (a classic token of that account with the public_repo scope;
the oan-helm repository is public, so any account can open a pull request from its fork). OAN_HELM_FORK is the name of the
fork (default oan-helm). DRY_RUN=1 prints the change and touches nothing.

Exit codes: 0 pull request open (or nothing to do), 1 unexpected failure, 3 no credential, 4 GitHub refused.

Standard library only; runs on the deploy node's stock Python (3.7 or later).
"""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SLUG = "Centre-for-Open-Societal-Systems/oan-helm"
CHART = "openg2p-livestock-registry"
VALUES_PATH = "charts/%s/values.yaml" % CHART
DIGESTS = ".build/image-digests.tsv"
PR_FILE = ".build/oan-helm-pr.txt"
# chart values section under `registry:` -> ECR component name
REGISTRY = (("staffApi", "staff-api"), ("partnerApi", "partner-api"), ("celeryWorker", "celery"),
            ("celeryBeat", "celery"), ("dbSeed", "db-seed"), ("staffUi", "staff-ui"), ("sanity", "sanity-tests"))
DASHBOARD = "dashboard-api"


class Stop(Exception):
    """A reason to stop with an exit code and a message for the build log."""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code


def load_bump():
    spec = importlib.util.spec_from_file_location("bump_pin", HERE / "bump_pin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---- the values file ---------------------------------------------------------------------------------------------

def read_digests(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2 or not re.fullmatch(r"sha256:[0-9a-f]{64}", parts[1].strip()):
            raise ValueError("bad digest line: " + line[:80])
        result[parts[0].strip()] = parts[1].strip()
    return result


def wanted(image_tag, digests):
    """{values section: 'commit@sha256:..'} for the registry components, plus the dashboard (tag, digest)."""
    if not re.fullmatch(r"[0-9a-f]{12}", image_tag):
        raise ValueError("IMAGE_TAG must be the 12-character commit tag")
    missing = sorted((set(c for _, c in REGISTRY) | {DASHBOARD}) - set(digests))
    if missing:
        raise ValueError("no ECR digest for: " + ", ".join(missing))
    tags = dict((section, "%s@%s" % (image_tag, digests[component])) for section, component in REGISTRY)
    return tags, (image_tag, digests[DASHBOARD])


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _block_end(lines, start, indent):
    """Index after the block that starts at `start`: the next non-blank line indented `indent` or less."""
    index = start + 1
    # Blank lines and comment lines (whatever their column) belong to the block they are in.
    while index < len(lines) and (not lines[index].strip() or lines[index].lstrip().startswith("#")
                                  or _indent(lines[index]) > indent):
        index += 1
    return index


def _find(lines, pattern, start, end):
    for index in range(start, end):
        if re.fullmatch(pattern, lines[index]):
            return index
    raise ValueError("values.yaml has no line matching %r" % pattern)


def _set_value(lines, start, end, key, value, indent):
    """Replace `<indent>key: ...` inside lines[start:end]; return True when the text changed."""
    found = _find(lines, r" {%d}%s: \S.*" % (indent, key), start, end)
    new = "%s%s: %s" % (" " * indent, key, value)
    changed = lines[found] != new
    lines[found] = new
    return changed


def rewrite_values(text, registry_tags, dashboard, repositories=None):
    """The values text with the new image tags; everything else is byte for byte as it was.

    `repositories` ({section: expected repository, 'dashboardApi': ...}) makes the rewrite refuse an image block whose
    repository is not the expected ECR repository.
    """
    lines = text.split("\n")
    top = _find(lines, r"registry:\s*", 0, len(lines))
    top_end = _block_end(lines, top, 0)
    for section, tag in registry_tags.items():
        header = _find(lines, r" {2}%s:\s*" % section, top + 1, top_end)
        end = _block_end(lines, header, 2)
        image = _find(lines, r" {4}image:\s*", header + 1, end)
        image_end = _block_end(lines, image, 4)
        if repositories and section in repositories:
            repo = lines[_find(lines, r" {6}repository: \S+", image + 1, image_end)].split(": ", 1)[1].strip()
            if repo != repositories[section]:
                raise ValueError("%s image repository is %s, expected %s" % (section, repo, repositories[section]))
        _set_value(lines, image + 1, image_end, "tag", tag, 6)
    header = _find(lines, r"dashboardApi:\s*", 0, len(lines))
    end = _block_end(lines, header, 0)
    image = _find(lines, r" {2}image:\s*", header + 1, end)
    image_end = _block_end(lines, image, 2)
    if repositories and "dashboardApi" in repositories:
        repo = lines[_find(lines, r" {4}repository: \S+", image + 1, image_end)].split(": ", 1)[1].strip()
        if repo != repositories["dashboardApi"]:
            raise ValueError("dashboardApi image repository is %s, expected %s" % (repo, repositories["dashboardApi"]))
    # Quoted: a tag of only digits (or 1234e5678901) would be read as a number, and the chart would render %!s(int64=...).
    _set_value(lines, image + 1, image_end, "tag", "'%s'" % dashboard[0], 4)
    _set_value(lines, image + 1, image_end, "digest", dashboard[1], 4)
    return "\n".join(lines)


def released_before(text, image_tag):
    """True when the values already carry this commit's images (an earlier build of the same commit released them)."""
    return re.search(r"(?m)^\s+tag: %s@sha256:[0-9a-f]{64}\s*$" % re.escape(image_tag), text) is not None


def _image_block(lines, section):
    """(start, end) of the lines inside the image block of a registry section, or of dashboardApi (section=None)."""
    if section is None:
        header = _find(lines, r"dashboardApi:\s*", 0, len(lines))
        end = _block_end(lines, header, 0)
        image = _find(lines, r" {2}image:\s*", header + 1, end)
        return image + 1, _block_end(lines, image, 2), 4
    top = _find(lines, r"registry:\s*", 0, len(lines))
    top_end = _block_end(lines, top, 0)
    header = _find(lines, r" {2}%s:\s*" % section, top + 1, top_end)
    end = _block_end(lines, header, 2)
    image = _find(lines, r" {4}image:\s*", header + 1, end)
    return image + 1, _block_end(lines, image, 4), 6


def _get_value(lines, start, end, key, indent):
    found = _find(lines, r" {%d}%s: \S.*" % (indent, key), start, end)
    return lines[found].split(": ", 1)[1].strip().strip("'\"")


def read_images(text):
    """The images a chart's values hold: ({section: 'commit@sha256:..'}, (dashboard tag, dashboard digest)).

    The inverse of rewrite_values; it refuses a tag that is not pinned by digest.
    """
    lines = text.split("\n")
    tags = {}
    for section, _ in REGISTRY:
        start, end, indent = _image_block(lines, section)
        tag = _get_value(lines, start, end, "tag", indent)
        if not re.fullmatch(r"[0-9a-f]{12}@sha256:[0-9a-f]{64}", tag):
            raise ValueError("%s image tag %r is not <commit12>@sha256:<digest>" % (section, tag))
        tags[section] = tag
    start, end, indent = _image_block(lines, None)
    dashboard = (_get_value(lines, start, end, "tag", indent), _get_value(lines, start, end, "digest", indent))
    if not re.fullmatch(r"[0-9a-f]{12}", dashboard[0]) or not re.fullmatch(r"sha256:[0-9a-f]{64}", dashboard[1]):
        raise ValueError("dashboardApi image is not <commit12> with a sha256 digest: %s %s" % dashboard)
    return tags, dashboard


def expected_repositories(registry, path):
    result = dict((section, "%s/%s/%s" % (registry, path, component)) for section, component in REGISTRY)
    result["dashboardApi"] = "%s/%s/%s" % (registry, path, DASHBOARD)
    return result


def archive_values(archive_bytes):
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        member = archive.getmember("%s/values.yaml" % CHART)
        if not member.isfile() or member.size > 2 * 1024 * 1024:
            raise ValueError("unexpected values.yaml in the chart archive")
        return archive.extractfile(member).read().decode("utf-8")


def carries(values_text, registry_tags, dashboard):
    """True when the values already hold exactly these images (rewriting them changes nothing)."""
    return rewrite_values(values_text, registry_tags, dashboard) == values_text


# ---- GitHub ------------------------------------------------------------------------------------------------------

def api(method, path, token, payload=None):
    request = urllib.request.Request("https://api.github.com" + path, method=method,
                                     data=json.dumps(payload).encode() if payload is not None else None)
    request.add_header("Authorization", "Bearer " + token)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except ValueError:
            body = {}
        return error.code, body


def refused(status, body, doing, repo=SLUG):
    message = (body or {}).get("message", "")
    if status in (401, 403, 404):
        raise Stop(4, "GitHub refused to %s on %s (HTTP %s: %s). The token needs the public_repo scope (classic token of the "
                      "account that owns the fork), and the fork must exist." % (doing, repo, status, message))
    raise Stop(1, "GitHub could not %s on %s (HTTP %s: %s)" % (doing, repo, status, message))


class Proposal(object):
    """Opens (or updates) the pull request from the fork's branch into oan-helm main."""

    def __init__(self, token, owner, fork_name="oan-helm", call=api, out=print):
        self.token, self.owner, self.call, self.out = token, owner, call, out
        self.fork = "%s/%s" % (owner, fork_name)
        self.note = None

    def upstream(self, method, path, payload=None):
        return self.call(method, "/repos/%s%s" % (SLUG, path), self.token, payload)

    def mine(self, method, path, payload=None):
        return self.call(method, "/repos/%s%s" % (self.fork, path), self.token, payload)

    # -- steps
    def main_head(self):
        status, body = self.upstream("GET", "/git/ref/heads/main")
        if status != 200:
            refused(status, body, "read oan-helm main")
        return body["object"]["sha"]

    def contents(self, repo_call, ref, repo):
        status, body = repo_call("GET", "/contents/%s?ref=%s" % (VALUES_PATH, ref))
        if status != 200:
            refused(status, body, "read " + VALUES_PATH, repo)
        return base64.b64decode(body["content"]).decode("utf-8"), body["sha"]

    def prepare_branch(self, branch, main_sha):
        """The fork's branch starts from the head of the org repo's main (created, or reset when it is left over)."""
        status, body = self.mine("POST", "/git/refs", {"ref": "refs/heads/" + branch, "sha": main_sha})
        if status in (200, 201):
            return
        message = str((body or {}).get("message", ""))
        if status == 422 and "already exists" in message:
            status, body = self.mine("PATCH", "/git/refs/heads/" + branch, {"sha": main_sha, "force": True})
            if status != 200:
                refused(status, body, "reset the branch " + branch, self.fork)
            return
        if status in (404, 422):
            # The fork cannot see that commit yet: bring the fork's main up to date with the org repo, then try again.
            self.out("The fork does not have oan-helm commit %s yet; syncing its main." % main_sha[:12])
            sync_status, sync_body = self.mine("POST", "/merge-upstream", {"branch": "main"})
            if sync_status not in (200, 201):
                raise Stop(4, "The fork %s cannot be brought up to date with %s (HTTP %s: %s). Use 'Sync fork' on GitHub, "
                              "then rerun the build." % (self.fork, SLUG, sync_status, (sync_body or {}).get("message", "")))
            status, body = self.mine("POST", "/git/refs", {"ref": "refs/heads/" + branch, "sha": main_sha})
            if status in (200, 201):
                return
            if status == 422 and "already exists" in str((body or {}).get("message", "")):
                status, body = self.mine("PATCH", "/git/refs/heads/" + branch, {"sha": main_sha, "force": True})
                if status == 200:
                    return
        refused(status, body, "create the branch " + branch, self.fork)

    def commit_values(self, branch, new_text, message):
        text, blob = self.contents(self.mine, branch, self.fork)
        if text != new_text:
            status, body = self.mine("PUT", "/contents/" + VALUES_PATH, {
                "message": message, "branch": branch, "sha": blob,
                "content": base64.b64encode(new_text.encode("utf-8")).decode("ascii")})
            if status not in (200, 201):
                refused(status, body, "commit the new image tags", self.fork)

    def open_pull_request(self, branch, title, body_text):
        head = "%s:%s" % (self.owner, branch)
        status, pulls = self.upstream("GET", "/pulls?state=open&head=%s" % head)
        if status != 200:
            refused(status, pulls, "list pull requests")
        if pulls:
            number = pulls[0]["number"]
            status, body = self.upstream("PATCH", "/pulls/%d" % number, {"title": title, "body": body_text})
            if status != 200:
                refused(status, body, "update the pull request")
            return pulls[0]["html_url"], False
        status, created = self.upstream("POST", "/pulls", {"title": title, "head": head, "base": "main",
                                                           "body": body_text, "maintainer_can_modify": True})
        if status not in (200, 201):
            refused(status, created, "open the pull request")
        return created["html_url"], True

    # -- the whole stage
    def run(self, env, root, digests_text):
        image_tag = env["IMAGE_TAG"]
        tags, dashboard = wanted(image_tag, read_digests(digests_text))
        repositories = expected_repositories(env["ECR_REGISTRY"], env.get("ECR_PATH", "openg2p/livestock-registry"))
        main_sha = self.main_head()
        text, _ = self.contents(self.upstream, "main", SLUG)
        new_text = rewrite_values(text, tags, dashboard, repositories)
        subject = env.get("COMMIT_SUBJECT", "").strip()[:100]
        self.out("images of build %s:" % image_tag)
        for section, tag in sorted(tags.items()):
            self.out("  %-13s %s" % (section, tag))
        self.out("  %-13s %s %s" % ("dashboardApi", dashboard[0], dashboard[1]))
        if released_before(text, image_tag):
            self.note = ("Commit %s is already in oan-helm main: a re-run or rebuild of the same commit opens no new pull "
                         "request." % image_tag)
            self.out(self.note)
            return None
        if env.get("DRY_RUN"):
            self.out("DRY_RUN: %s would change on %s." % (VALUES_PATH, SLUG))
            return None
        branch = "bot/livestock-images-" + image_tag
        title = "Livestock registry images %s%s" % (image_tag, (": " + subject) if subject else "")
        body = "\n".join([
            "Image tags and digests of Livestock Registry develop build `%s` (source commit `%s`)." % (
                image_tag, env.get("SOURCE_COMMIT", image_tag)),
            "", "Jenkins build: %s" % env.get("BUILD_URL", "(unknown)"), "",
            "Opened by the develop Jenkins build of livestock-registry after it pushed these images to ECR and deployed them to "
            "New Dev successfully. Only the image `tag` (and the dashboard `digest`) lines of `%s` change. Merging releases "
            "the next `%s` chart." % (VALUES_PATH, CHART), ""])
        self.prepare_branch(branch, main_sha)
        self.commit_values(branch, new_text, title)
        url, created = self.open_pull_request(branch, title, body)
        self.out(("pull request opened: " if created else "pull request updated: ") + url)
        return url


def main(env=None, root=ROOT, call=api):
    env = dict(os.environ if env is None else env)
    root = Path(root)
    try:
        for name in ("IMAGE_TAG", "ECR_REGISTRY"):
            if not env.get(name):
                raise Stop(1, name + " is not set")
        dry = bool(env.get("DRY_RUN"))
        if not dry and not (env.get("GH_TOKEN") and env.get("GH_USER")):
            raise Stop(3, "No GitHub credential (GH_USER = the account that owns the oan-helm fork, GH_TOKEN = its token): "
                          "no pull request was opened.")
        digests = (root / DIGESTS).read_text(encoding="utf-8")
        proposal = Proposal(env.get("GH_TOKEN", ""), env.get("GH_USER", "dry-run"), env.get("OAN_HELM_FORK", "oan-helm"),
                            call=call)
        url = proposal.run(env, root, digests)
        if url:
            target = root / PR_FILE
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(url + "\n", encoding="utf-8")
        return 0
    except Stop as stop:
        print("FAIL: %s" % stop)
        return stop.code
    except (ValueError, KeyError, OSError) as error:
        print("FAIL: %s: %s" % (error.__class__.__name__, error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
