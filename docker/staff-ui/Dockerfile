# Livestock Registry — Staff Portal UI image.
#
# Thin extension of the registry-platform staff-ui image. The Next.js app itself
# is used unchanged; this image only overrides presentation that the platform
# bakes in rather than exposing through the theme.
#
# WHY THIS IMAGE EXISTS
# Branding reaches the UI two ways. Colours, logo, favicon and the dashboard
# illustration are THEME DATA — seeded into the registry DB, editable at runtime
# under Configuration -> Theme. The page background is NOT: the dashboard paints
# it with a compiled Tailwind class,
#   bg-primary-first bg-[url('/images/common/bg_pattern.png')]
# which tiles a small tile at its natural size. A photograph needs
# background-size: cover, and there is no class or theme key for that — so the
# rule has to be overridden in the compiled stylesheet.
#
# Build context = repo root (matching the other docker/*/Dockerfile images).
ARG RP_VERSION=0.0.0-develop.296
FROM openg2p/openg2p-registry-staff-ui:${RP_VERSION}

# Browser-facing origin of the dashboard service, compiled into the client bundle
# by patch-dashboard-nav.js below — so changing it needs a rebuild, not a restart.
ARG DASHBOARD_URL=http://localhost:3001
ARG DASHBOARD_LABEL=Dashboard

COPY --chown=nextjs:nodejs docker/staff-ui/assets/livestock_bg.jpg /app/public/images/common/livestock_bg.jpg

# Repoint the dashboard background at the photo and make it cover the viewport.
#
# The override is appended to whichever compiled stylesheet already references
# bg_pattern, so it lands after the original rule and wins on cascade order at
# equal specificity. The selector matches on the Tailwind arbitrary-value class
# name itself — that class literally contains "bg_pattern", and it is the only
# thing on the page that does.
#
# This is coupled to someone else's build output, and the failure is SILENT: a
# platform bump that renames the class or drops the rule would leave the
# override matching nothing and the stock tile back. Assert the contract so a
# bump fails the build instead of the design review.
# The stylesheet is served `Cache-Control: immutable, max-age=1y` under a
# content-hashed name. Appending to it post-build changes the bytes but NOT the
# URL, so every browser that has already loaded the page keeps the stale CSS
# forever — a hard refresh does not necessarily re-fetch an immutable asset.
# So the file is also RENAMED and every reference in the build output rewritten,
# which is what makes the new rule actually reach the browser.
RUN set -eu; \
    css="$(grep -rl 'bg_pattern' /app/.next/static/css/ || true)"; \
    if [ -z "$css" ]; then \
      echo "FATAL: no compiled stylesheet references bg_pattern — override would be dead"; exit 1; \
    fi; \
    for f in $css; do \
      printf '%s' \
        '[class*="bg_pattern"]{' \
        'background-image:linear-gradient(rgba(0,0,0,.30),rgba(0,0,0,.30)),url("/images/common/livestock_bg.jpg")!important;' \
        'background-size:cover!important;' \
        'background-repeat:no-repeat!important;' \
        'background-position:center center!important;' \
        'background-attachment:fixed!important;' \
        '}' >> "$f"; \
      old="$(basename "$f" .css)"; new="${old}ls1"; \
      grep -rl "$old" /app/.next 2>/dev/null | while read -r ref; do \
        sed -i "s/${old}/${new}/g" "$ref"; \
      done; \
      mv "$(dirname "$f")/${old}.css" "$(dirname "$f")/${new}.css"; \
      echo "background override appended; stylesheet ${old}.css -> ${new}.css (busts the immutable cache)"; \
    done

# ── Add the Dashboard header button ─────────────────────────────────────────
# Puts a Dashboard control immediately left of Configuration, pointing at the
# dashboard-ui service. The dashboard is a separate origin — the portal ships as
# a finished build and cannot be extended with new routes — so the target is
# baked in here rather than resolved as a portal route.
#
# Runs AFTER the stylesheet rename above: that step rewrites references by CSS
# basename, so it is unaffected by the chunk edits this makes. The patch itself
# exits non-zero unless it matches at least two bundles (the header is a client
# component, emitted into both a static and a server chunk — patching only one
# trips a hydration mismatch), so a base-image change fails the build instead of
# silently dropping the button.
COPY --chown=nextjs:nodejs docker/staff-ui/assets/patch-dashboard-nav.js /tmp/patch-dashboard-nav.js
RUN DASHBOARD_URL="${DASHBOARD_URL}" DASHBOARD_LABEL="${DASHBOARD_LABEL}" \
    node /tmp/patch-dashboard-nav.js
