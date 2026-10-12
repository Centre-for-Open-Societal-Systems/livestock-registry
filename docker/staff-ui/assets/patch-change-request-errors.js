#!/usr/bin/env node
/*
 * Show why a change request was refused.
 *
 * On a register record, Edit Details > Save posts the section to
 * /api/change-request/create (or .../core-section/create). The portal sends
 * it through its fetch hook, whose execute() swallows an error response and
 * returns undefined; the page then shows nothing at all (registry-platform
 * 1.2) or only "Failed to create change request!" (296), although the
 * registry answers with the reason, e.g.
 *   400 {"statusText":"fayda_fan_id must be exactly 16 digits, ..."}
 *
 * This replaces that one call in the compiled record page with a plain
 * same-origin fetch to the same route, with the same body. A success is
 * handled exactly as before (toast_cr_created, then the form closes); a
 * refusal now shows the registry's message in an error toast and leaves the
 * form open so the value can be corrected.
 *
 * Exits non-zero if the call no longer has the expected shape, so a base
 * image change fails the build instead of silently losing the message.
 */
const fs = require("fs");
const path = require("path");

const ROOT = "/app/.next/static/chunks";
const files = [];
(function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) walk(p);
    else if (name.endsWith(".js")) {
      const src = fs.readFileSync(p, "utf8");
      if (src.includes('"/api/change-request/create"') && src.includes('"toast_cr_created"')) files.push(p);
    }
  }
})(ROOT);
if (files.length !== 1) {
  console.error(`patch-change-request-errors: expected 1 chunk with the change request save, found ${files.length}`);
  process.exit(1);
}

const FILE = files[0];
const src = fs.readFileSync(FILE, "utf8");
// B=await c(q,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({register_id:i,...})});
// B?.change_request_id&&(b.oR.success(r("toast_cr_created"),{position:"top-right",autoClose:6e3}),e())
const re = /(\w+)=await \w+\((\w+),\{method:"POST",headers:\{"Content-Type":"application\/json"\},body:JSON\.stringify\((\{register_id:[^}]*\})\)\}\);\1\?\.change_request_id&&\((\w+)\.oR\.success\((\w+)\("toast_cr_created"\)/;
const m = src.match(re);
if (!m) {
  console.error("patch-change-request-errors: change request save has an unexpected shape; refusing to patch");
  process.exit(1);
}
const [whole, result, url, body, toastMod, t] = m;
const replacement =
  `${result}=await(async()=>{let __lrRes,__lrJson=null;` +
  `try{__lrRes=await fetch(${url},{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify(${body})});` +
  `try{__lrJson=await __lrRes.json()}catch(__lrE){}}` +
  `catch(__lrE){${toastMod}.oR.error(String(__lrE&&__lrE.message||__lrE),{position:"top-right",autoClose:8e3});return null}` +
  `if(!__lrRes.ok||!__lrJson||!__lrJson.change_request_id){` +
  `${toastMod}.oR.error((__lrJson&&(__lrJson.statusText||__lrJson.message||__lrJson.error))||"Failed to create change request",{position:"top-right",autoClose:8e3});return null}` +
  `return __lrJson})();` +
  `${result}?.change_request_id&&(${toastMod}.oR.success(${t}("toast_cr_created")`;
const out = src.replace(whole, replacement);
if (out === src || out.split("__lrJson.change_request_id").length !== 2) {
  console.error("patch-change-request-errors: replacement did not apply cleanly");
  process.exit(1);
}
fs.writeFileSync(FILE, out);
console.log(`OK: change request save shows the registry's refusal message (${path.basename(FILE)})`);
