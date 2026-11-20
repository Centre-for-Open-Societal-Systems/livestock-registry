#!/usr/bin/env bash
# Ensure .app has node_modules matching package-lock.json.
set -euo pipefail

ui_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
app_dir="$ui_root/.app"
modules="$app_dir/node_modules"
lockfile="$app_dir/package-lock.json"
stamp="$app_dir/.deps-stamp"

say() { local a= b=; [[ -t 1 ]] && a=$'\033[36m' b=$'\033[0m'; printf '%s%s [staff-ui]%s %s\n' "$a" "$(date +%H:%M:%S)" "$b" "$*"; }
fail() { local a= b=; [[ -t 1 ]] && a=$'\033[31m' b=$'\033[0m'; printf '%s%s [staff-ui]%s %s\n' "$a" "$(date +%H:%M:%S)" "$b" "$*" >&2; exit 1; }

if [[ ! -f "$app_dir/package.json" ]]; then
    fail "Missing .app/ — clone did not produce a package.json"
fi

# The pinned staff-ui takes @openg2p/notification from the develop branch of
# OpenG2P/notifications (raw/refs/heads/develop/client/openg2p-notification-0.1.0.tgz).
# That file was removed from develop on 17 Nov 2026 (a97bb2f), so npm answered 404.
# Read the same tarball from the last commit that holds it; its sha512 is the one the
# lock file already records, so npm ci still verifies it. Same fix as Farmer Registry #322 and Crop sown.
# Remove once the pinned staff-ui (deps.json) points at the new package location.
notification_client_commit=01c678abac3d4d8ede40e00645f1ba73246f741b
pin_files=("$app_dir/package.json")
[[ -f "$lockfile" ]] && pin_files+=("$lockfile")
for pin_file in "${pin_files[@]}"; do
    sed "s#notifications/raw/refs/heads/develop/client/#notifications/raw/$notification_client_commit/client/#g" \
        "$pin_file" > "$pin_file.tmp"
    mv "$pin_file.tmp" "$pin_file"
done
if grep -q "notifications/raw/refs/heads/" "${pin_files[@]}"; then
    fail "@openg2p/notification still points at a branch of OpenG2P/notifications"
fi

file_sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

expected=""
[[ -f "$lockfile" ]] && expected=$(file_sha256 "$lockfile")
current=""
[[ -f "$stamp" ]] && current=$(tr -d '[:space:]' < "$stamp")

if [[ -d "$modules" && -n "$expected" && "$current" == "$expected" ]]; then
    say "Dependencies already installed"
    exit 0
fi

say "Installing dependencies…"
( cd "$app_dir" && npm ci --no-audit --no-fund --loglevel=error )
say "Dependencies installed"
if [[ -n "$expected" ]]; then
    printf '%s' "$expected" > "$stamp"
fi
