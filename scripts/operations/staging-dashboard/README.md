# Existing staging dashboard access

Staging's installed dashboard is the unmanaged `live/livestock-dashboard-ui`
Deployment and Service at `https://livestock-dashboard.oanstaging.com`.
Its original `nahom25/livestock-dashboard-ui:0.2.0` application serves data without
checking the registry's IAM session. It is separate from the standalone dashboard
delivery configured for New Dev.

`access-proxy.mjs` protects this existing application using staging's shared staff
IAM and the existing `livestock-registry-staff-portal` client roles. The allowed
roles are those carrying `register:view` in the registry IAM registration:
Data Editor, Data Validator, Data Supervisor, Operations Administrator and
Technical Administrator. The existing staff `admin` already carries the last
two roles. This operation creates no users, clients or role mappings.

The access process runs alongside the existing application in the same Pod,
using the digest of its already-running image. It validates the staff session
through IAM before forwarding to port 3000. The existing Service targets the
authenticated port 8080; its selector and public VirtualService are preserved.
The application container, database configuration and chart release are retained.
Only `/api/health` is public. Other API requests require a session and viewing
role; pages redirect to the existing IAM login. IAM failures deny access.

Run the tests before applying from an authorized staging deployment agent:

```sh
node --test scripts/operations/staging-dashboard/access-proxy.test.mjs
python3 scripts/operations/staging-dashboard/deploy.py --apply
```

The deployment program verifies the installed image, unmanaged ownership,
Service selector, port and Node runtime. It snapshots the existing Deployment,
Service and VirtualService under a private, unique directory on `vpn-agent2` and
prints that backup location. It starts the guard before changing the Service.
A rollout failure restores the exact previous Pod template and Service ports,
and removes the task ConfigMap. The operation rejects an already-modified
deployment instead of overwriting it.

Verify the public route redirects to login, chart requests without a session
return 401, and a session without registry viewing access returns 403. A fresh
staff session with a viewing role must retrieve the unchanged chart response.
Staff login credentials are not required to deploy the access guard. Do not
reset the staff account to perform verification.

For recovery, use the printed private snapshot directory. Verify the Deployment
and Service UIDs still match their snapshots before replacing
`spec.template` and `spec.ports` with the saved values. Wait for that Deployment
rollout, then delete only `live/livestock-dashboard-access`. Keep the snapshots
for audit. No standalone dashboard promotion or seed-hook retry is part of this
operation.
