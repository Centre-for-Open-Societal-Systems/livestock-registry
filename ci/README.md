# CI

What checks a change to this repository, and where each check runs. Chart delivery is in
[deploy/README.md](deploy/README.md), the connector release in [connector/README.md](connector/README.md).

## Where checks run

| Runner | Trigger | What it runs |
| --- | --- | --- |
| GitHub Actions, [`checks.yml`](../.github/workflows/checks.yml) | every push and pull request | `contracts`: `ci/validate.sh`, the connector chart render, and in the [test image](refactor/profile-tests.Dockerfile): `livestock-extension/tests`, the native metadata rehearsal and the signed HTTP onboarding gate. `chart`: Helm dependency build, lint and render. |
| GitHub Actions, [`dashboard-delivery.yml`](../.github/workflows/dashboard-delivery.yml) | every push and pull request | `test/test_oan_chart.py` and `test/test_deployment_guard.py`. |
| Jenkins, [`Jenkinsfile`](../Jenkinsfile) | one multibranch job | `staging` branch: [`pipelines/staging.groovy`](pipelines/staging.groovy). Everything else, including pull requests: [`pipelines/dev.groovy`](pipelines/dev.groovy), which starts with the chart version check and `validate.sh --native` in the test image. Only `develop` goes on to build, deploy to New Dev and publish the chart. Neither deploys until every GitHub check of the commit is green ([`deploy/require-green-checks.sh`](deploy/require-green-checks.sh)). |
| Jenkins, [`Jenkinsfile.operator`](../Jenkinsfile.operator) | started by hand only, after approval by `admin` | Operator actions: `fresh-install` (drops the New Dev databases), `connector-plan`, `connector-upgrade` ([`pipelines/operator.groovy`](pipelines/operator.groovy)). |

## validate.sh

The offline gate. It needs no cloud credentials or network, and Jenkins mounts the repository read-only. In order:

1. `ruff check .`, with the rules in [`ruff.toml`](../ruff.toml) (below).
2. `pytest test ci/connector/tests`, except `test/sanity`, which runs against a deployment. With a coverage report
   (below).
3. `odk/test_transform.py`: the ODK transform against the sample submissions.
4. `node --test`: the staff UI widget tests and the staging dashboard access proxy. They need Node 22.18 or later, so
   they run on GitHub only; the Jenkins test image has no Node.
5. With `--native` only, in the test image: `pytest livestock-extension/tests`, with a coverage report.
6. `refactor/check_port.py`, and `bash -n` on every shell script under `ci/` and `ui/staff-ui/scripts/`.

Run it locally from the repository root with Python 3.12 and the packages that `checks.yml` installs:

```bash
bash ci/validate.sh             # source checks
bash ci/validate.sh --native    # in the test image, which has the platform packages
```

### Lint

`ruff check .` covers every Python file of the repository except the vendored PyYAML (`deploy/vendor`). It enforces
only rules that find mistakes (pyflakes, comparisons to `None`/`True`, bare `except`, pylint errors), and only rules
the code passes today. Two pyflakes rules are not enforced yet: unused imports and f-strings without placeholders.
`ruff.toml` lists them with their counts. Clearing one and removing it from `ignore` makes it enforced.

### Guard tests

Some tests in `test/` guard contracts between files that nothing checks at runtime. A break there fails silently in a
deployment, so the test names what broke:

| Test | Guards |
| --- | --- |
| `test_rp_pin_lockstep.py` | The platform version agrees across the chart, the Dockerfiles, the pipelines and `ci/refactor`, and `scripts/bump-rp-version.sh` moves every copy. |
| `test_metadata_consistency.py` | The platform's base model columns match the platform pin; widget data paths, register schemas and the reporting views name real columns; the models yield every register. |
| `test_child_register_keys.py` | The DCI template reads child registers under the keys the platform attaches them by (known gaps are listed in the test). |
| `test_seed_on_conflict.py` | Every INSERT in `meta_data/` and `awe_meta_data/` has ON CONFLICT, so the db-seed can replay. |
| `test_consent_scopes.py` | Every consent scope id named in the repository is a top-level key of the DCI search response. |
| `test_search_text.py` | `search_text` is built only from real columns, and raw register INSERTs write it. |
| `test_awe_policy_keys.py` | Registry approval bindings, AWE policies, stages and approver rules join on `policy_key`. |

### Coverage

Both pytest runs report line coverage of `livestock-extension/src` and enforce no minimum. A minimum is to be agreed.
The baseline on 2026-11-25, of 6,150 statements on Python 3.12:

| Run | Where | Coverage |
| --- | --- | --- |
| `test/` and `ci/connector/tests` | `validate.sh`, GitHub and Jenkins | 1% |
| `livestock-extension/tests` | the test image: GitHub's native step and `validate.sh --native` in Jenkins | 50% |

`test/` checks files and deployment scripts more than it imports the extension, so its figure stays low. The
extension's own tests need the platform packages and run only in the test image. The second figure is the one a
minimum would apply to.

## Folders

| Folder | Contents |
| --- | --- |
| `pipelines/` | The Jenkins pipelines the `Jenkinsfile`s load |
| `deploy/` | Chart packaging and publication, the pinned central chart, the New Dev deploy and rollback |
| `connector/` | The livestock-connector release, its chart and tests |
| `dashboard/` | Dashboard API and UI verification and deploy |
| `refactor/` | The test image, metadata rehearsal, onboarding and deployment guards |
| `k8s/` | Service accounts, RBAC and the connector client secret for the dev deploy |
| `migrations/` | One-off SQL migrations |
| `image_names.py`, `ecr_repository.py` | The ECR names of the images and the settings of their repositories |
| `check-new-dev-routes.py`, `check-farmer-enrichment.py` | Guards on rendered manifests: public routing (the New Dev deploy runs it) and Farmer enrichment settings |
| `validate.sh` | The offline gate above |
