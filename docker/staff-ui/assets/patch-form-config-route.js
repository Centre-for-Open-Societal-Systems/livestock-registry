#!/usr/bin/env node
/*
 * Let the portal's /api/attributes/values route reach the livestock
 * extension's form-config endpoint.
 *
 * The dialog overlay (livestock-dialog-overlay.js) needs two livestock facts
 * per code-list value that Master Data does not carry: whether a species
 * requires an ear tag / is a flock species, and a vaccine's interval in days.
 * Since registry-platform 1.2 the code lists come from Master Data, so the
 * registry serves those facts itself at POST /livestock/form-config
 * (register_domain/controllers/g2p_form_config_controller.py), in the same
 * envelope shape as Master Data's attribute values.
 *
 * The browser only talks to the portal's own Next.js routes, and the portal
 * has no generic backend proxy, so this adds one switch to the compiled
 * /api/attributes/values route: called with ?livestock=form-config it proxies
 * to the registry backend's /livestock/form-config instead of Master Data's
 * /attributes/get_attribute_values. Everything else about the route (auth,
 * payload, response transform) is unchanged.
 *
 * Exits non-zero if the route no longer has the expected shape, so a base
 * image change fails the build instead of leaving the overlay without config.
 */
const fs = require("fs");

const FILE = "/app/.next/server/app/api/attributes/values/route.js";
const src = fs.readFileSync(FILE, "utf8");

// async function x(a){return(0,w.a)({req:a,backend:"masterdata",targetEndpoint:"/attributes/get_attribute_values",
const re = /async function (\w+)\((\w+)\)\{return\((0,\w+\.\w+)\)\(\{req:\2,backend:"masterdata",targetEndpoint:"\/attributes\/get_attribute_values",/;
const m = src.match(re);
if (!m) {
  console.error("patch-form-config-route: /api/attributes/values route has an unexpected shape; refusing to patch");
  process.exit(1);
}
const [whole, fn, arg, call] = m;
const replacement =
  `async function ${fn}(${arg}){let livestockCfg=!!(${arg}.nextUrl&&${arg}.nextUrl.searchParams&&${arg}.nextUrl.searchParams.get("livestock")==="form-config");` +
  `return(${call})({req:${arg},backend:livestockCfg?"default":"masterdata",targetEndpoint:livestockCfg?"/livestock/form-config":"/attributes/get_attribute_values",`;
const out = src.replace(whole, replacement);
if (out === src || out.split("/livestock/form-config").length !== 2) {
  console.error("patch-form-config-route: replacement did not apply cleanly");
  process.exit(1);
}
fs.writeFileSync(FILE, out);
console.log("OK: /api/attributes/values?livestock=form-config -> registry /livestock/form-config");
