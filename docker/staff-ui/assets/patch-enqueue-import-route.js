#!/usr/bin/env node
/*
 * Let File Import actually queue the uploaded file.
 *
 * New Intake -> File Import uploads the CSV / Excel, then calls the portal's
 * Next.js route /api/input-mechanism/enqueue-import, which rebuilds the
 * request from a fixed field list and sends only `document_store_id`. The
 * registry API (/input-mechanism-data/enqueue_import_file) requires
 * `document_id` -- the catalog id the upload also returns -- so every import
 * was rejected with "Field required" while the dialog still said "Import
 * Successful", and nothing was ever queued.
 *
 * The route now forwards `document_id` as well; livestock-dialog-overlay.js
 * adds it to the browser's request (it remembers the document_id each upload
 * returned for its document_store_id). Undefined values disappear in
 * JSON.stringify, so a request without it behaves exactly as before.
 *
 * Exits non-zero if the route no longer has the expected shape, so a
 * base-image change fails the build instead of leaving File Import dead.
 */
const fs = require("fs");

const FILE = "/app/.next/server/app/api/input-mechanism/enqueue-import/route.js";
const FROM = "request_payload:{document_store_id:a.document_store_id,";
const TO = "request_payload:{document_id:a.document_id,document_store_id:a.document_store_id,";

const before = fs.readFileSync(FILE, "utf8");
if (before.includes(TO)) {
  console.log("  already patched enqueue-import");
} else {
  const hits = before.split(FROM).length - 1;
  if (hits !== 1) {
    console.error(`FATAL: enqueue-import/route.js has ${hits} occurrences of the payload head, expected 1`);
    process.exit(1);
  }
  fs.writeFileSync(FILE, before.replace(FROM, TO));
  console.log("  patched enqueue-import");
}
