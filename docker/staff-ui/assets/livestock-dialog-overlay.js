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
 *   - Animal dialog: choosing a Species hides the breeds of other species;
 *     the read-only Age field is filled live from Date of Birth as it is
 *     typed (same "N years, M months" text the server stores on save).
 *   - Event dialogs (Health / Vaccination / Vital / Breeding): a dropdown of
 *     this submission's animals sits under the Ear Tag field (typing still
 *     works, with suggestions); once a tag names one of those animals the
 *     read-only Species and Age fields are filled from it (the server fills
 *     the same two columns on save) and its breed / sex are shown beside it;
 *     on the Vaccination dialog the Vaccine list is narrowed to that
 *     animal's species.
 *
 * The read-only fields are the platform's display widgets (plain text, "-"
 * when empty); they are written directly and re-applied whenever the dialog
 * re-renders, since the platform has no way to derive them itself.
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
        if (tag && !seen[tag]) {
          seen[tag] = true;
          out.push({ tag: tag, species: o.species || "", breed: o.breed || "", gender: o.gender || "", dob: o.date_of_birth || "", age: o.age || "" });
        }
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
  function ageFrom(dob) {
    if (!dob) return "";
    var d = new Date(dob); if (isNaN(d.getTime())) return "";
    var now = new Date(); var years = now.getFullYear() - d.getFullYear(); var months = now.getMonth() - d.getMonth();
    if (now.getDate() < d.getDate()) months -= 1;
    if (months < 0) { years -= 1; months += 12; }
    if (years < 0) return "";
    return years + " years, " + months + " months"; // same text the server stores (format_age)
  }
  function describeRest(a) {
    var parts = [];
    if (a.breed) parts.push(pretty(a.breed, "LIVESTOCK_BREED_"));
    if (a.gender) parts.push(pretty(a.gender, ""));
    return parts.join(" \u00b7 ");
  }
  function describe(a) {
    var parts = [pretty(a.species, "LIVESTOCK_SPECIES_")];
    if (a.breed) parts.push(pretty(a.breed, "LIVESTOCK_BREED_"));
    if (a.gender) parts.push(pretty(a.gender, ""));
    var age = a.age || ageFrom(a.dob); if (age) parts.push("age " + age);
    return parts.join(" \u00b7 ");
  }
  var CONTROL_CLASS = "w-full sm:w-[180px] max-w-full h-[30px] px-3 border shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white";
  function infoLine(id) {
    var el = document.createElement("div"); el.id = id; el.className = "text-sm text-gray-600 mt-1"; el.style.minHeight = "1.25rem"; return el;
  }
  function pretty(id, prefix) { return String(id || "").replace(prefix, "").replace(/_/g, " ").toLowerCase().replace(/\b\w/g, function (c) { return c.toUpperCase(); }); }
  // Read-only cells in the dialog ("Species:", "Age:") are display widgets:
  // <div class="widget-container" data-widget-id="..-dlg-N-<key>"> .. <div class="flex-1"><div title="-">-</div>
  // Remember what we wrote per dialog+key and re-apply after each re-render.
  function displayCell(dialog, key) {
    var box = dialog.querySelector('.widget-container[data-widget-id$="-' + key + '"]');
    return box ? box.querySelector(".flex-1 > div") : null;
  }
  function setDisplay(dialog, key, text) {
    var want = dialog.__lrDisplay || (dialog.__lrDisplay = {});
    want[key] = text;
    applyDisplay(dialog);
  }
  function applyDisplay(dialog) {
    var want = dialog.__lrDisplay; if (!want) return;
    Object.keys(want).forEach(function (key) {
      var cell = displayCell(dialog, key); if (!cell) return;
      var text = want[key] || "-";
      if (cell.textContent !== text) { cell.textContent = text; cell.title = text; }
    });
  }
  function keepDisplay(dialog) {
    if (dialog.__lrDisplayObserver) return;
    dialog.__lrDisplayObserver = new MutationObserver(function () { applyDisplay(dialog); });
    dialog.__lrDisplayObserver.observe(dialog, { childList: true, subtree: true, characterData: true });
  }

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
    var dob = control(dialog, /^Date of Birth\b/, "input");
    if (dob) {
      keepDisplay(dialog);
      var showAge = function () { setDisplay(dialog, "age", ageFrom(dob.value)); };
      dob.addEventListener("input", showAge); dob.addEventListener("change", showAge); showAge();
    }
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

      // a real dropdown of this form's animals + a description line, under the field
      var box = ear.parentElement; while (box && box.parentElement && !/flex-1/.test(box.className)) box = box.parentElement;
      var host = box || ear.parentElement;
      var pick = document.createElement("select"); pick.className = CONTROL_CLASS + " mt-1"; pick.id = "lr-animal-pick";
      var ph = document.createElement("option"); ph.value = ""; ph.textContent = animals.length ? "Pick an animal of this form\u2026" : "No animals saved on this form yet"; pick.appendChild(ph);
      animals.forEach(function (a) { var o = document.createElement("option"); o.value = a.tag; o.textContent = a.tag + " \u2014 " + describe(a); pick.appendChild(o); });
      var info = infoLine("lr-animal-info");
      host.appendChild(pick); host.appendChild(info);
      var find = function () { var t = String(ear.value || "").trim().toUpperCase(); for (var i = 0; i < animals.length; i++) if (animals[i].tag === t) return animals[i]; return null; };
      keepDisplay(dialog);
      var reflect = function () {
        var a = find(); var t = String(ear.value || "").trim();
        pick.value = a ? a.tag : "";
        setDisplay(dialog, "species", a ? pretty(a.species, "LIVESTOCK_SPECIES_") : "");
        setDisplay(dialog, "age", a ? (a.age || ageFrom(a.dob)) : "");
        info.textContent = a ? describeRest(a) : (t ? "Not an animal of this form \u2014 add it under Livestock Details first" : "");
        info.style.color = a || !t ? "" : "#b91c1c";
      };
      pick.addEventListener("change", function () { if (pick.value) setValue(ear, pick.value); reflect(); });
      ear.addEventListener("input", reflect); ear.addEventListener("change", reflect); reflect();

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
