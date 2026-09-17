/*
 * Livestock dialog overlay — runs in the browser on top of the official Staff
 * Portal (openg2p-registry-staff-ui), injected at image build time by
 * patch-dialog-overlay.js and served from /livestock-dialog-overlay.js.
 *
 * Why it exists: inside dialog-table pop-ups the platform cannot cascade one
 * column from another (Species -> Breed / Vaccine) nor list another section's
 * rows (the ear tag of this form's animals). The livestock metadata therefore
 * ships plain, unfiltered lists and a typed ear tag, and the SERVER enforces
 * every rule (breed/vaccine must belong to the species, the ear tag must be an
 * animal of this submission). This script only restores the guidance on
 * screen; if it fails or is absent nothing breaks.
 *
 *   - Animal dialog: choosing a Species hides the breeds of other species.
 *   - Event dialogs (Health / Vaccination / Vital / Breeding): the typed Ear
 *     Tag gets a suggestion list of this submission's animals; on the
 *     Vaccination dialog the Vaccine list is narrowed to that animal's species.
 *
 * Data comes only from the portal's own endpoints (same-origin, same session):
 *   POST /api/attributes/values               -> every value with parent_value_id
 *   POST /api/intake-form/get-intake-form-submission -> this submission's rows
 * The submission id is read from the URL on a reopened draft, or captured from
 * the response of each section save on a new form.
 */
(function () {
  "use strict";
  if (window.__livestockDialogOverlay) return;
  window.__livestockDialogOverlay = true;

  var DIALOG = ".fixed.inset-0";
  var BREED_ATTR = "LIVESTOCK_BREED";
  var VACCINE_ATTR = "VACCINE_TYPE";
  var cache = { values: {}, animals: {}, submissionId: null };

  var m = location.pathname.match(/\/intake-form\/[^/]+\/submission\/([0-9a-fA-F-]{36})/);
  if (m) cache.submissionId = m[1];

  var nativeFetch = window.fetch;
  window.fetch = function (input) {
    var p = nativeFetch.apply(this, arguments);
    try {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      if (url.indexOf("/api/intake-form/save-intake-form-submission") > -1) {
        p.then(function (res) {
          if (!res || !res.ok) return;
          res.clone().json().then(function (j) {
            if (j && j.submission_id) { cache.submissionId = j.submission_id; cache.animals = {}; }
          }).catch(function () {});
        }).catch(function () {});
      }
    } catch (e) { /* never break the portal */ }
    return p;
  };

  function post(path, body) {
    return nativeFetch(path, {
      method: "POST", credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.ok ? r.json() : null; });
  }
  function attributeValues(attr) {
    if (!cache.values[attr]) {
      cache.values[attr] = post("/api/attributes/values", { attribute_id: attr, page_size: 500 })
        .then(function (j) { return Array.isArray(j) ? j : (j && j.attributeValues) || []; })
        .catch(function () { return []; });
    }
    return cache.values[attr];
  }
  function submissionAnimals() {
    var id = cache.submissionId;
    if (!id) return Promise.resolve([]);
    if (!cache.animals[id]) {
      cache.animals[id] = post("/api/intake-form/get-intake-form-submission", { submission_id: id })
        .then(extractAnimals).catch(function () { return []; });
    }
    return cache.animals[id];
  }
  function extractAnimals(json) {
    var out = [], seen = {};
    (function walk(o) {
      if (Array.isArray(o)) { o.forEach(walk); return; }
      if (!o || typeof o !== "object") return;
      // an animal row: has ear_tag_id + breed, and is not an event row
      if (o.ear_tag_id && ("breed" in o) && !("event_type" in o) && !("vaccine_type" in o)) {
        var tag = String(o.ear_tag_id).trim().toUpperCase();
        if (tag && !seen[tag]) { seen[tag] = true; out.push({ tag: tag, species: o.species || "", breed: o.breed || "" }); }
      }
      Object.keys(o).forEach(function (k) { walk(o[k]); });
    })(json);
    return out;
  }
  function byParent(list) {
    var map = {};
    list.forEach(function (v) {
      if (!v || !v.value_id) return;
      var p = v.parent_value_id || "";
      (map[p] = map[p] || {})[v.value_id] = true;
    });
    return map;
  }
  function pretty(id, prefix) { return String(id || "").replace(prefix, "").replace(/_/g, " ").toLowerCase().replace(/\b\w/g, function (c) { return c.toUpperCase(); }); }

  // ---- DOM helpers -------------------------------------------------------
  function control(dialog, labelRe, selector) {
    var labels = dialog.querySelectorAll("label");
    for (var i = 0; i < labels.length; i++) {
      if (labelRe.test(labels[i].textContent.replace(/\s+/g, " ").trim())) {
        var box = labels[i].parentElement;
        return box ? box.querySelector(selector) : null;
      }
    }
    return null;
  }
  function setValue(el, value) {
    var proto = el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
  }
  function restrictOptions(select, allowed) {
    var opts = select.options;
    for (var i = 0; i < opts.length; i++) {
      var o = opts[i];
      if (!o.value) continue;
      var ok = !allowed || !!allowed[o.value];
      o.hidden = !ok; o.disabled = !ok;
    }
    if (allowed && select.value && !allowed[select.value]) setValue(select, "");
  }
  function observeOptions(select, apply) {
    new MutationObserver(function () { apply(); }).observe(select, { childList: true });
  }

  // ---- Animal dialog: Species -> Breed ------------------------------------
  function wireAnimal(dialog) {
    var species = control(dialog, /^Species\b/, "select");
    var breed = control(dialog, /^Breed\b/, "select");
    if (!species || !breed) return;
    attributeValues(BREED_ATTR).then(function (list) {
      var map = byParent(list);
      var apply = function () { var s = species.value; restrictOptions(breed, s ? (map[s] || {}) : null); };
      species.addEventListener("change", apply);
      observeOptions(breed, apply);
      apply();
    });
  }

  // ---- Event dialogs: Ear Tag suggestions (+ Vaccine by species) -----------
  function wireEvent(dialog) {
    var ear = control(dialog, /Ear Tag\b/, "input");
    if (!ear) return;
    submissionAnimals().then(function (animals) {
      var dl = document.getElementById("lr-ear-tag-suggestions");
      if (!dl) { dl = document.createElement("datalist"); dl.id = "lr-ear-tag-suggestions"; document.body.appendChild(dl); }
      dl.innerHTML = "";
      animals.forEach(function (a) {
        var o = document.createElement("option");
        o.value = a.tag;
        o.label = pretty(a.species, "LIVESTOCK_SPECIES_") + (a.breed ? " / " + pretty(a.breed, "LIVESTOCK_BREED_") : "");
        dl.appendChild(o);
      });
      ear.setAttribute("list", "lr-ear-tag-suggestions");
      ear.setAttribute("autocomplete", "off");
      if (animals.length && !ear.getAttribute("placeholder")) ear.setAttribute("placeholder", "Pick or type an ear tag of this form");

      var vaccine = control(dialog, /^Vaccine\b/, "select");
      if (!vaccine) return;
      attributeValues(VACCINE_ATTR).then(function (list) {
        var map = byParent(list);
        var apply = function () {
          var tag = String(ear.value || "").trim().toUpperCase();
          var a = null;
          for (var i = 0; i < animals.length; i++) if (animals[i].tag === tag) { a = animals[i]; break; }
          restrictOptions(vaccine, a && a.species ? (map[a.species] || {}) : null);
        };
        ear.addEventListener("input", apply);
        ear.addEventListener("change", apply);
        observeOptions(vaccine, apply);
        apply();
      });
    });
  }

  // ---- watch for dialogs -----------------------------------------------------
  var wired = new WeakSet();
  function scan() {
    var dialogs = document.querySelectorAll(DIALOG);
    for (var i = 0; i < dialogs.length; i++) {
      var d = dialogs[i];
      if (wired.has(d)) continue;
      if (!d.querySelector("label")) continue; // not rendered yet
      wired.add(d);
      try {
        if (control(d, /^Breed\b/, "select")) wireAnimal(d);
        else if (control(d, /Ear Tag\b/, "input")) wireEvent(d);
      } catch (e) { /* overlay must never break the dialog */ }
    }
  }
  new MutationObserver(scan).observe(document.documentElement, { childList: true, subtree: true });
  scan();
})();
