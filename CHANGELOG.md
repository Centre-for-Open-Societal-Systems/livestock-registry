# Changelog

Notable changes to the Livestock Registry, newest first, in the format of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions are the repository version in `init.yaml` (see [release](docs/release.md)). Before this file, the history is
the git log and the pull requests.

## [Unreleased]

### Added

- `ci/validate.sh` runs every test in `test/` (#264).
- Guard tests for contracts between files that nothing checks at runtime (#265):
  - base model columns match the platform pin; widget data paths, register schemas and the reporting views name real
    columns;
  - the DCI template reads child registers under the keys the platform attaches them by;
  - every seed INSERT has ON CONFLICT;
  - consent scope ids are releasable by the DCI search response;
  - `search_text` is built from real columns;
  - AWE policy keys join across the registry and AWE seeds;
  - every copy of the platform version follows the pin.
- Coverage reports of `livestock-extension/src`, with no minimum yet, and a lint over every Python file with the
  rules in `ruff.toml`. `ci/README.md`: where each check runs (#266).
- `docs/deployment.md`, `docs/release.md` and this changelog.

### Changed

- `scripts/bump-rp-version.sh` moves every copy of the platform version (the pipelines, `ci/refactor` and the
  Dockerfiles), not only the Dockerfiles and the `Jenkinsfile` (#265).

### Fixed

- The schema migration test that the legacy table rename drops and deletes nothing matched a backspace character
  instead of a word boundary, so it could never fail (#266).

### Known issues

- The DCI search response's `farmer_info` (phone number, surname, sex, birth date) is always empty: Farmer is not a
  child register of Livestock, so the platform never attaches it to the holding. The given name falls back to the
  holding's `farmer_name`. Listed in `test/test_child_register_keys.py` (`KNOWN_UNATTACHED`).
