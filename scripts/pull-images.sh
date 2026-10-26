#!/usr/bin/env bash
# Pull compose images one at a time, retrying on transient registry errors.
#
# Docker pulls every service's image concurrently, opening far more parallel TLS
# connections than a slow or lossy link can complete. The handshakes then time out
# ("net/http: TLS handshake timeout") even though the registry itself is healthy.
# Pulling serially keeps the connection count low; retries pick up where a failed
# attempt stopped, since completed layers stay in the local cache.

set -uo pipefail

cd "$(dirname "$0")/.."

RETRIES="${RETRIES:-8}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

mapfile -t IMAGES < <(
  grep -oE 'image: *[^ ]+' "$COMPOSE_FILE" |
    awk '{print $2}' |
    grep -v -- '-local:dev' |
    sort -u
)

echo "Pulling ${#IMAGES[@]} images serially (up to $RETRIES attempts each)."
echo

failed=()
for image in "${IMAGES[@]}"; do
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo "✔ $image (already present)"
    continue
  fi

  for attempt in $(seq 1 "$RETRIES"); do
    echo "→ $image (attempt $attempt/$RETRIES)"
    if docker pull "$image"; then
      echo "✔ $image"
      break
    fi

    if [ "$attempt" -eq "$RETRIES" ]; then
      echo "✘ $image — gave up after $RETRIES attempts"
      failed+=("$image")
      break
    fi

    # Back off so a congested link gets a chance to drain between attempts.
    backoff=$((attempt * 5))
    echo "  retrying in ${backoff}s..."
    sleep "$backoff"
  done
  echo
done

if [ "${#failed[@]}" -gt 0 ]; then
  echo "Failed images:"
  printf '  %s\n' "${failed[@]}"
  exit 1
fi

echo "All images pulled. Run: docker compose up"
