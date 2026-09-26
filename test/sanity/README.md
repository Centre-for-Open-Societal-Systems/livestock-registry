# Livestock Registry — sanity tests (field-specific, Set 2)

The Livestock Registry does **not** carry its own copy of the sanity suite. The
registry-platform publishes the whole suite as an image,
`openg2p/openg2p-registry-sanity-tests`, containing:

- the **harness** — signing, DCI envelope building, PM/CM/Keycloak/AWE seeding,
  DB helpers, step logging, and the `conftest.py` banners/fixtures;
- **Set 1 (extension-independent tests)** — `test_smoke.py` and
  `test_e2e_negative.py`: liveness, wiring, and the fail-closed cases (search
  without consent / bad signature / wrong audience is rejected). These are
  identical for every registry and run unchanged.

This directory holds only **Set 2 — the Livestock Registry's field-specific
parts**, which `docker/sanity-tests/Dockerfile` layers onto that base image
(overwriting the reference registry's versions at the same paths):

| File | What is livestock-specific |
|---|---|
| `sanity/fixtures.py`  | the seeded record + the `g2p_register_livestocks` tables |
| `sanity/data_seed.py` | idempotent injection into `g2p_register_livestocks` |
| `tests/test_e2e_dci.py` | the livestock DCI template nests the farmer identity under `<scope>.farmer_info.demographic_info` |
| `tests/test_e2e_change_request.py` | the register/history rows are verified in the livestock tables |

Everything else (register id, DCI reg-type, search text, consent scopes, CR
tab/section) is **configuration**, supplied as env by the Helm chart's `sanity.*`
values — not baked here.
