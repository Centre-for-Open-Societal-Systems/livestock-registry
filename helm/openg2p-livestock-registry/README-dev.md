# Deploying the Livestock Registry to the dev cluster

The dev cluster is the OpenG2P gen2 sandbox box (`65.2.237.75`), namespace
`live`. The Jenkins job's **Deploy to Development** stage installs the in-repo
chart there as the release `livestock-registry`, with `values-dev.yaml` layered
on top of the chart's own `values.yaml`.

| | |
| --- | --- |
| Public dev URL | `https://livestock-registry-development.oanstaging.com` |
| Public IAM | `https://staff-iam-livestock-development.oanstaging.com` |
| Public Keycloak | `https://keycloak-livestock-development.oanstaging.com` |
| Internal staff API | `https://staff-livestock-registry.live.openg2p.test` (WireGuard) |
| Internal partner API | `https://partner-livestock-registry.live.openg2p.test` (WireGuard) |

All three public names resolve to the box and carry Let's Encrypt certificates
terminated by nginx, which proxies to the Istio ingress gateway.

## Why the dev URL used to show stale code

The dev URL and the dev *release* were two separate things.

`helm upgrade --install` did run on every merge and the new pods did start, but
the chart's default hostnames put them on `*.live.openg2p.org` — a domain that
does not exist on this box, and one the `internal` Istio Gateway (which admits
only `live.openg2p.test` and `*.live.openg2p.test`) would not have accepted
anyway. So all four of the release's VirtualServices bound to nothing.

Meanwhile `livestock-registry-development.oanstaging.com` was served by a
hand-applied VirtualService, `pub-staff-portal-ui`, pointing at
`farmer-registry-staff-portal-ui-pub` — a hand-cloned Deployment of the August
release, running `docker.io/nahom25/livestock-staff-ui:0.2.0`. That never
changed, so the URL never changed.

Repointing that VirtualService at the new release would not have been enough on
its own: the new release's UI was configured end to end for `.openg2p.org` —
`APP_URL`, `COOKIE_DOMAIN`, `IAM_URL`, `KEYCLOAK_LOGOUT_URL`, `REDIRECT_URL` —
so the browser would have been redirected to hostnames it cannot resolve and
login would have failed immediately. The hostnames had to be fixed first, which
is what `values-dev.yaml` does.

## One-time cutover step

`values-dev.yaml` makes the release's own staff-ui VirtualService claim the
public dev hostname. The hand-applied one still claims it too, and two
VirtualServices on the same host and Gateway with the same prefix conflict —
the older one wins. Delete it once, after the first build carrying this file
has deployed:

```sh
kubectl -n live delete virtualservice pub-staff-portal-ui
```

After that, every merge to `develop` reaches the dev URL by itself. Nothing
about this step needs repeating, and nothing in CI depends on it having been
done — the deploy simply has no visible effect until it is.

Two objects are then left over from the August arrangement and can be removed
whenever convenient. They cost a pod each and are no longer routed:

```sh
kubectl -n live delete deploy,svc farmer-registry-staff-portal-ui-pub
helm -n live uninstall farmer-registry     # the whole August release
```

`commons-services-iam-staff-portal-api-pub` is **not** in that list: it still
serves `staff-iam-livestock-development.oanstaging.com`, which the new release
uses.

## Verifying a deploy

```sh
helm -n live status livestock-registry
kubectl -n live get vs livestock-registry-staff-portal-ui \
  -o jsonpath='{.spec.hosts[0]} -> {.spec.http[0].route[0].destination.host}{"\n"}'

# Login must be tested at /api/login, not at / -- the static Next.js page
# returns 200 even when login is completely broken.
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  'https://livestock-registry-development.oanstaging.com/api/login?redirect_uri=https://livestock-registry-development.oanstaging.com'
```

Expect `307` to
`keycloak-livestock-development.oanstaging.com/realms/staff/protocol/openid-connect/auth`
with `code_challenge_method=S256`.

## Known gaps on dev, not addressed here

* **MinIO is not reachable from a browser.** `global.minioHost` points at the
  in-cluster Service so that db-seed can upload at all; the external host
  presents the box's self-signed CA, which the seed's S3 client rejects. The
  registry hands out pre-signed URLs built from that host, so document and
  photo links do not open from outside the cluster. This was already true
  before — `live` has no public nginx block for MinIO at all. Fixing it needs a
  public MinIO hostname on the box, not a values change.
* **`live` runs its own Keycloak**, separate from the shared `commons` one. Its
  `login_providers` row 2 is the public issuer, which is why
  `staffUi.envVars.LOGIN_PROVIDER_ID` is `2` here and `1` in the chart default.
