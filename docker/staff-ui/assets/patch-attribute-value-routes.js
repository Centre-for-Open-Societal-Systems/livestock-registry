#!/usr/bin/env node
/*
 * Let the Attribute Values create/update proxy routes forward the vaccine
 * schedule fields (interval_days / is_active / notes) and the species config
 * fields (requires_ear_tag / is_flock_species).
 *
 * The Staff Portal never calls the registry API directly: its Next.js routes
 *   /api/configuration/attributes/create-attribute-value
 *   /api/configuration/attributes/update-attribute-value
 * rebuild the request from a fixed field list (attribute_id, value_code,
 * value_display, parent_value_id, sort_order, ...), so anything else in the
 * browser's request body is silently dropped before it reaches the backend.
 * That is what made Interval (days) / Active / Notes — added to the dialog by
 * livestock-dialog-overlay.js — save nothing while the Species (which is a
 * field the route already knows: parent_value_id) did.
 *
 * The backend already accepts interval_days / is_active / notes (see
 * docker/staff-api/core-patches/apply_patches.py), so the only missing piece is
 * the pass-through, added here to the compiled route bundles. Undefined values
 * disappear in JSON.stringify, so dialogs that do not send them are unaffected.
 *
 * Exits non-zero if a route no longer has the expected shape, so a base-image
 * change fails the build instead of leaving the fields dead again.
 */
const fs = require("fs");
const path = require("path");

const ROOT = "/app/.next/server/app/api/configuration/attributes";
const ROUTES = ["create-attribute-value", "update-attribute-value"];
const FROM = "sort_order:a.sort_order??0}}";
const TO =
  "sort_order:a.sort_order??0,interval_days:a.interval_days,is_active:a.is_active,notes:a.notes," +
  "requires_ear_tag:a.requires_ear_tag,is_flock_species:a.is_flock_species}}";

for (const route of ROUTES) {
  const file = path.join(ROOT, route, "route.js");
  const before = fs.readFileSync(file, "utf8");
  if (before.includes(TO)) { console.log("  already patched " + route); continue; }
  const hits = before.split(FROM).length - 1;
  if (hits !== 1) {
    console.error(`FATAL: ${route}/route.js has ${hits} occurrences of the payload tail, expected 1`);
    process.exit(1);
  }
  fs.writeFileSync(file, before.replace(FROM, TO));
  console.log("  patched " + route);
}
