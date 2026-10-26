# Livestock Registry refactor

`develop-refactor` starts at OpenG2P Farmer 1.2 `ed1e70ccf18df5476fa404ed8018e12d55e418fa` and ports curated
domain source from `35d21bbe07853324d9493279630fe35600d98c0f`. Legacy develop ancestry is not merged.

This is an incomplete source port and **cannot be promoted or installed**.
See [the current delivery candidate](docs/refactor-candidate.md) for the latest
source, Helm, popup-only FIN and verification boundaries.
The seed preflight stops before any database mutation. See
[the blockers](docs/refactor/STATUS.json) and [source decisions](docs/refactor/SOURCE_MAP.json).
Existing Jenkins deployment branches, credential references, ECR repositories,
deployment scripts and preservation guards are retained. This branch builds and
validates only; no existing environment was replaced.

Domain models/schemas/UUIDs and portable rules are preserved. Platform workers,
core code and compiled UI assets are not patched. Legacy bulk import,
Keycloak-location approval and optional Farmer lookup paths are retired.
Native IMPORT_FILE must cover all supported channels with the same Farmer
dependency rules before acceptance. Farmer remains authoritative and unchanged.

Local projects: Commons, Farmer, Crop and Livestock. Run serially with Commons +
Farmer + Crop, then Commons + Farmer + Livestock; at most two registries at once.
Do not rerender or replace the running Farmer stack from this worktree.

See [New Dev parity and source ownership](docs/refactor/NEW_DEV_PARITY_AND_CLEANUP.md)
for the verified 316 fields, registered schema/location widgets and preserved
source cleanup. Helm lives in COSS oan-helm; this repository consumes exact
archives through [the central profile](ci/deploy/oan-chart.json). Deployment
remains blocked until the explicit acceptance requirements pass.
