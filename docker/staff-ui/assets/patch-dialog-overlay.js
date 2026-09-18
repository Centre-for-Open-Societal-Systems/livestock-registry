#!/usr/bin/env node
/*
 * Load /livestock-dialog-overlay.js on every Staff Portal page.
 *
 * Same mechanism as patch-dashboard-nav.js: the portal header's right-hand
 * control list — `(0,r.jsxs)("div",{className:"flex items-center gap-8",
 * children:[ ... ]})` — exists in one server chunk and one static chunk. A
 * null child is inserted as its first child whose evaluation, on the client
 * only and once per page load, appends a real <script src defer> to <head>
 * via the DOM. (A React-rendered <script> element would never load: React
 * creates client-side script elements inert by design, and the header is not
 * part of the server HTML.) The app router keeps the header mounted across
 * client-side navigation, so the script's own MutationObserver covers every
 * dialog that opens later.
 * (The header is only rendered for signed-in users, which is exactly where the
 * dialogs live.) The file itself is copied to /app/public by the Dockerfile.
 *
 * Runs AFTER patch-dashboard-nav.js, which may already have renamed the static
 * chunk (".dashboard.js"); the pattern still matches, and the static chunk is
 * renamed once more (".overlay.js") so the immutable-cache name changes.
 * Exits non-zero if fewer than two bundles match.
 */
const fs = require("fs");
const path = require("path");
const ROOT = "/app/.next";
const SRC = "/livestock-dialog-overlay.js";
const PATTERN =
  /(\(0,(\w+)\.jsxs\)\("div",\{className:"flex items-center gap-8",children:\[)/g;
// NOT a React <script> element: React creates client-rendered script elements
// inert on purpose (they never load). Instead a null child whose evaluation
// appends a real <script> via the DOM, once, on the client only.
const tag = () =>
  `("undefined"!=typeof window&&!window.__lrOverlayTag&&(window.__lrOverlayTag=1,` +
  `setTimeout(function(){var s=document.createElement("script");s.src=${JSON.stringify(SRC)};s.defer=!0;document.head.appendChild(s)},0)),null),`;
function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (entry.name.endsWith(".js")) yield full;
  }
}
let patched = 0;
const renamed = [];
for (const file of walk(ROOT)) {
  const before = fs.readFileSync(file, "utf8");
  if (!before.includes("flex items-center gap-8") || before.includes(SRC)) continue;
  const after = before.replace(PATTERN, (_m, open) => open + tag());
  if (after !== before) {
    fs.writeFileSync(file, after);
    patched += 1;
    console.log("  patched " + file.replace(ROOT + "/", ""));
    if (file.includes(`${path.sep}static${path.sep}`)) {
      const ext = path.extname(file);
      const next = file.slice(0, -ext.length) + ".overlay" + ext;
      fs.renameSync(file, next);
      renamed.push({ from: path.basename(file), to: path.basename(next) });
      console.log("  renamed " + path.basename(file) + " -> " + path.basename(next));
    }
  }
}
if (patched < 2) {
  console.error(`dialog-overlay patch matched ${patched} bundle(s), expected at least 2 — the base image header layout changed`);
  process.exit(1);
}
for (const { from, to } of renamed) {
  let refs = 0;
  for (const file of walk(ROOT)) {
    const before = fs.readFileSync(file, "utf8");
    if (!before.includes(from)) continue;
    fs.writeFileSync(file, before.split(from).join(to));
    refs += 1;
  }
  console.log(`  rewrote ${refs} reference(s) to ${from}`);
}
if (!fs.existsSync("/app/public" + SRC)) {
  console.error(`overlay file missing at /app/public${SRC} — copy it before running this patch`);
  process.exit(1);
}
console.log(`loading ${SRC} from ${patched} bundle(s)`);
