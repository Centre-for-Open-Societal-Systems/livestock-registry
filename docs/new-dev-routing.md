# New-dev registry routing

The existing `livestock-registry` release in namespace `livestock` uses:

| Component | Host |
| --- | --- |
| Staff UI | `livestock-registry.development.oanstaging.com` |
| Staff API | `staff-livestock.development.oanstaging.com` |
| Partner API | `partner-livestock.development.oanstaging.com` |
| ID generator | `idgenerator-livestock.development.oanstaging.com` |

All four VirtualServices use `istio-system/development`. The Jenkins new-dev
stage reads `helm/openg2p-livestock-registry/values-new-dev.yaml`, which supplies
these hosts/Gateways, canonical shared Keycloak/IAM/MinIO URLs and the cookie
domain `.development.oanstaging.com`. Private Service/database addresses,
Secret references, component images and registry-platform dependency pins are
unchanged. The generic chart and live/staging values remain separate.

Before `helm upgrade`, Jenkins converts the exact render to JSON with
`kubectl create --dry-run=client --validate=false` and runs the stdlib-only
`ci/check-new-dev-routes.py`. This rejects missing/wrong registry routes, old
public URLs (including encoded login configuration), old cookie scope, public
routes on the wrong Gateway and private routes on the shared public Gateway.
Only resource counts/status are logged; manifests and Secret values are not.
Python 3 and kubectl must be available on the deployment node.

Additional private overrides must be reconciled with this public profile;
replacing a custom list can discard live settings. Legacy browser redirects and
API proxy aliases remain environment-owned compatibility resources: retain
them until migration completion is explicitly confirmed. Keep the existing
release name and namespace; do not install a second release over its resources.

This fixes future new-dev deployment inputs; merging a PR is not a deployment.
The existing deploy behavior for images, initialization/seed hooks, credentials
and resource ownership remains in place. A normal app rollout may run migrations
or seed hooks. For a separate URL-only repair, back up the current release and
suppress both hooks and ordinary initialization Jobs; TTL-cleaned Jobs can be
recreated even when their manifests have not changed. Helm rollback cannot undo
database migrations.

Run the guard's adversarial tests without cluster access:

```sh
python3 test/test_new_dev_routes.py
```

Validate the actual render with the same deployment guard before a rollout, then
run `scripts/check-registry-public-urls.py` from the OAN Helm repository. That
read-only live Postman regression verifies canonical UI/API routes and temporary
old URL compatibility. Rendering alone does not prove live public reachability.
