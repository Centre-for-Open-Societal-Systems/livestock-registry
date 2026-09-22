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
 *     animal's species, and Next Due Date is filled as Vaccination Date +
 *     the vaccine's configured interval.
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
  var attrExtra = null; // set while a Configuration -> Attribute Values dialog carries our extra fields
  window.fetch = function (input, init) {
    var args = arguments;
    var isAttrSave = false;
    try {
      var saveUrl = typeof input === "string" ? input : (input && input.url) || "";
      if (/configuration\/attributes\/(create|update)-attribute-value/.test(saveUrl)) {
        isAttrSave = true;
        if (attrExtra && document.body.contains(attrExtra.dialog) && init && typeof init.body === "string") {
          var body = JSON.parse(init.body), extra = attrExtra.read();
          Object.keys(extra).forEach(function (k) { body[k] = extra[k]; });
          args = [input, Object.assign({}, init, { body: JSON.stringify(body) })];
        }
      }
    } catch (e) { /* never break the portal */ }
    var p = nativeFetch.apply(this, args);
    if (isAttrSave) p.then(function () { cache.values = {}; }).catch(function () {});
    try {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      if (url.indexOf("/api/intake-form/save-intake-form-submission") > -1) {
        // the portal sends the submission id with every section save
        try {
          var sent = init && typeof init.body === "string" ? JSON.parse(init.body) : null;
          if (sent && sent.submission_id) { cache.submissionId = sent.submission_id; cache.animals = {}; }
        } catch (e2) { /* ignore */ }
        p.then(function (res) {
          if (!res || !res.ok) return;
          res.clone().json().then(function (j) {
            var sid = j && (j.submission_id || (j.response_payload && j.response_payload.submission_id));
            if (sid) { cache.submissionId = sid; cache.animals = {}; }
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
    wireSpeciesFields(dialog, species);
    wireDialogRegistrationDate(dialog);
  }

  // ---- Animal dialog: what identifies the animal depends on its species -------
  // The species' own config (Configuration > Attribute Values > Species: "Requires
  // Ear Tag" / "Flock / Group Species") decides the form, exactly as the server
  // enforces it (G2PRegisterDomainServiceAnimal):
  //   ear-tagged species     Ear Tag (required), Sex = Male / Female
  //   no-ear-tag species     Secondary Identifier (leg band, wing tag, hive number, ...)
  //                          instead of the Ear Tag, Sex may also be Mixed
  //   flock / group species  Quantity (head count) is asked for, Date of Birth is optional
  // The platform cannot show/hide dialog fields from another field's config, so the
  // fields are all rendered and this shows the ones that apply.
  function fieldBox(dialog, labelRe) {
    var labels = dialog.querySelectorAll("label");
    for (var i = 0; i < labels.length; i++) {
      if (!labelRe.test(labels[i].textContent.replace(/\s+/g, " ").trim())) continue;
      // the whole grid cell, so a hidden field leaves no gap in the two-column layout
      var cell = labels[i].closest(".widget-container");
      return (cell && cell.parentElement) || labels[i].parentElement;
    }
    return null;
  }
  function markRequired(box, on) {
    if (!box) return;
    var label = box.querySelector("label"), mark = label && label.querySelector(".lr-req");
    if (on && label && !mark && !/\*/.test(label.textContent)) {
      mark = document.createElement("span"); mark.className = "lr-req"; mark.textContent = "*"; mark.style.color = "#dc2626"; mark.style.marginLeft = "4px";
      label.appendChild(mark);
    } else if (!on && mark) mark.remove();
  }
  function wireSpeciesFields(dialog, species) {
    var earInput = control(dialog, /^Livestock Ear Tag\b/, "input");
    var secInput = control(dialog, /^Secondary Identifier\b/, "input");
    var qtyInput = control(dialog, /^Quantity\b/, "input");
    var dobInput = control(dialog, /^Date of Birth\b/, "input");
    var sex = control(dialog, /^Sex\b/, "select");
    var earBox = fieldBox(dialog, /^Livestock Ear Tag\b/), secBox = fieldBox(dialog, /^Secondary Identifier\b/);
    var qtyBox = fieldBox(dialog, /^Quantity\b/), dobBox = fieldBox(dialog, /^Date of Birth\b/);
    if (!earInput || !secInput || !qtyInput) return; // an older / customised form: leave it alone
    var msg = document.createElement("div"); msg.className = "text-sm mt-2"; msg.style.color = "#b91c1c"; msg.style.minHeight = "1.25rem";
    var save = null;
    var buttons = dialog.querySelectorAll("button");
    for (var b = 0; b < buttons.length; b++) if (/^Save\b/.test(buttons[b].textContent.trim())) save = buttons[b];
    if (save && save.parentElement) save.parentElement.parentElement.insertBefore(msg, save.parentElement);

    var byId = {}, cfg = { ear: true, flock: false };
    var current = function () {
      var v = byId[species.value];
      cfg = { ear: !(v && v.requires_ear_tag === false), flock: !!(v && v.is_flock_species === true) };
      return cfg;
    };
    var apply = function () {
      var c = current(), chosen = !!species.value;
      if (earBox) earBox.style.display = c.ear ? "" : "none";
      if (secBox) secBox.style.display = c.ear || !chosen ? "none" : "";
      if (qtyBox) qtyBox.style.display = c.flock ? "" : "none";
      markRequired(earBox, c.ear); markRequired(secBox, !c.ear && chosen); markRequired(qtyBox, c.flock); markRequired(dobBox, !c.flock);
      if (!c.ear && chosen && earInput.value) setValue(earInput, "");
      if ((c.ear || !chosen) && secInput.value) setValue(secInput, "");
      if (!c.flock && qtyInput.value) setValue(qtyInput, "");
      if (sex) restrictOptions(sex, c.ear ? { MALE: true, FEMALE: true } : { MALE: true, FEMALE: true, MIXED: true });
      msg.textContent = "";
    };
    attributeValues("LIVESTOCK_SPECIES").then(function (list) {
      list.forEach(function (v) { if (v && v.value_id) byId[v.value_id] = v; });
      species.addEventListener("change", apply);
      if (sex) observeOptions(sex, apply);
      apply();
    });

    // The dialog's own Save only checks the platform's static "required" flags, which
    // cannot follow the species; block it here with the reason (the server checks too).
    if (save) save.addEventListener("click", function (e) {
      var c = current(), blank = function (el) { return !el || !String(el.value || "").trim(); }, problem = "";
      if (species.value) {
        if (c.ear && blank(earInput)) problem = "Livestock Ear Tag is required for this species.";
        else if (!c.ear && blank(secInput)) problem = "Secondary Identifier (leg band, wing tag, hive number, ...) is required — this species has no ear tag.";
        else if (c.flock && !(parseInt(qtyInput.value, 10) > 0)) problem = "Quantity (head count) is required for this species.";
        else if (!c.flock && dobInput && blank(dobInput)) problem = "Date of Birth is required for this species.";
      }
      if (problem) { e.preventDefault(); e.stopImmediatePropagation(); msg.textContent = problem; }
    }, true);
  }

  // Registration Date starts as today in the Add dialog (an Edit keeps the saved date).
  // The platform's "today" default does not fill the picker itself.
  function wireDialogRegistrationDate(dialog) {
    var reg = control(dialog, /^Registration Date\b/, "input");
    if (!reg) return;
    var today = writeDate(reg, new Date()), touched = false, tries = 0;
    if (reg.type === "date") reg.max = today;
    reg.addEventListener("input", function (e) { if (e.isTrusted) touched = true; });
    var timer = setInterval(function () {
      if (!document.body.contains(dialog) || touched || ++tries > 8) { clearInterval(timer); return; }
      if (!reg.value) setValue(reg, today); else clearInterval(timer);
    }, 250);
  }

  // ---- Vaccination dialog: Next Due Date = Vaccination Date + vaccine interval ----
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function readDate(el) {
    var v = String(el.value || "").trim(), p;
    if ((p = v.match(/^(\d{4})-(\d{2})-(\d{2})/))) return new Date(+p[1], +p[2] - 1, +p[3]);
    if ((p = v.match(/^(\d{2})\/(\d{2})\/(\d{4})$/))) return new Date(+p[3], +p[2] - 1, +p[1]);
    return null;
  }
  function writeDate(el, d) {
    return el.type === "date"
      ? d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
      : pad2(d.getDate()) + "/" + pad2(d.getMonth() + 1) + "/" + d.getFullYear();
  }
  // The interval is set per vaccine under Configuration -> Attribute Values
  // (VACCINE_TYPE -> Edit -> Interval / Active). The server recomputes the same
  // value on save; this only shows it while the dialog is open.
  function wireNextDueDate(dialog, vaccine, vaccineValues) {
    var given = control(dialog, /^Vaccination Date\b/, "input");
    var next = control(dialog, /^Next Due Date\b/, "input");
    if (!given || !next) return;
    var days = {};
    vaccineValues.forEach(function (v) {
      var n = Number(v && v.interval_days);
      if (v && v.value_id && n > 0 && v.is_active !== false) days[v.value_id] = n;
    });
    // Vaccination Date starts as today (the platform's "today" default does not
    // fill the picker); set once so the user can still change or clear it.
    if (!given.value) setValue(given, writeDate(given, new Date()));
    // A vaccination cannot have happened in the future (the server rejects it too):
    // the picker stops at today and a typed later date is pulled back to today.
    if (given.type === "date") given.max = writeDate(given, new Date());
    var clampToToday = function () {
      var d = readDate(given), now = new Date();
      if (d && d > new Date(now.getFullYear(), now.getMonth(), now.getDate())) setValue(given, writeDate(given, now));
    };
    given.addEventListener("change", clampToToday);
    given.addEventListener("blur", clampToToday);
    var apply = function () {
      var n = days[vaccine.value], base = readDate(given);
      if (!n || !base) return;
      var want = writeDate(next, new Date(base.getFullYear(), base.getMonth(), base.getDate() + n));
      if (next.value !== want) setValue(next, want);
    };
    vaccine.addEventListener("change", apply);
    given.addEventListener("input", apply);
    given.addEventListener("change", apply);
    // the platform fills the "today" default after the dialog first renders
    var timer = setInterval(function () {
      if (!document.body.contains(dialog)) { clearInterval(timer); return; }
      apply();
    }, 400);
    apply();
  }

  // ---- Event dialogs: Ear Tag suggestions (+ Vaccine by species) -----------
  // ---- Vital Event dialog: Event Date defaults to today once Event Type is picked ----
  // Event Date is hidden until Event Type has a value (see
  // patch_ls_vital_event_details_sync_ui_schema.sql) and the platform's
  // "today" default (widget-data-default) does not fill the picker itself, only
  // the server resolves it on save -- same gap as Registration Date elsewhere.
  function wireVitalEventDate(dialog) {
    var eventType = control(dialog, /^Event Type\b/, "select");
    if (!eventType) return; // not this dialog
    var touchedFields = new WeakSet();
    // Event Date does not exist in the DOM at all until Event Type has a value
    // (a real mount/unmount, not a CSS hide -- confirmed by its label being
    // absent from a blank dialog's own label list). Selecting Event Type
    // triggers the platform's own re-render that mounts it, so it is not there
    // yet when this "change" fires; poll for it the same way
    // wireDialogRegistrationDate / wireNextDueDate wait out the platform's own
    // re-render elsewhere in this file.
    var tryFill = function () {
      if (!document.body.contains(dialog)) return;
      var eventDate = control(dialog, /^Event Date\b/, "input");
      if (!eventDate || touchedFields.has(eventDate)) return;
      var today = writeDate(eventDate, new Date());
      if (eventDate.type === "date") eventDate.max = today;
      eventDate.addEventListener("input", function (e) { if (e.isTrusted) touchedFields.add(eventDate); });
      if (eventType.value && !eventDate.value) setValue(eventDate, today);
    };
    eventType.addEventListener("change", function () {
      var tries = 0;
      var timer = setInterval(function () {
        if (!document.body.contains(dialog) || ++tries > 10) { clearInterval(timer); return; }
        tryFill();
      }, 200);
    });
    tryFill(); // Edit: the dialog can reopen with Event Type already set
  }

  // ---- Breeding dialog: Outcome only shows once the calving date has passed ----
  // Outcome (PENDING/SUCCESSFUL/FAILED) means nothing before the pregnancy
  // could plausibly have ended -- shown once Breeding Type is picked (see
  // g2p_register_sections.sql) so it mounts, then hidden by this overlay
  // until Expected Calving Date is today or earlier. "Today" isn't something
  // the platform's own show/hide condition engine can express (its
  // conditions only compare a field to another field or a fixed value baked
  // into the form config, never the current date -- see the note on
  // bt()/br() in patch_ls_health_event_details_sync_ui_schema.sql), so this
  // is done here instead.
  function startOfToday() { var n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); }
  function wireBreedingOutcome(dialog) {
    if (!control(dialog, /^Breeding Type\b/, "select")) return; // not this dialog
    // Re-applied on every dialog mutation, not just Expected Calving Date's own
    // "input"/"change": an unrelated field mounting/unmounting elsewhere in this
    // same conditional column list (e.g. Pregnancy Confirmation Date appearing
    // when Pregnancy Confirmed flips to Yes) can shift the platform's own
    // reconciliation enough to remount Outcome's DOM node too, silently
    // dropping a one-time inline style set on the old node -- same reasoning
    // as keepDisplay/applyDisplay for the read-only Species/Age cells above.
    var apply = function () {
      var calving = control(dialog, /^Expected Calving Date\b/, "input");
      var outcomeBox = fieldBox(dialog, /^Outcome\b/);
      if (!calving || !outcomeBox) return;
      var d = readDate(calving);
      var passed = !!d && d <= startOfToday();
      if (outcomeBox.style.display !== (passed ? "" : "none")) outcomeBox.style.display = passed ? "" : "none";
      if (!passed) {
        var sel = outcomeBox.querySelector("select");
        if (sel && sel.value) setValue(sel, "");
      }
    };
    if (!dialog.__lrOutcomeObserver) {
      dialog.__lrOutcomeObserver = new MutationObserver(apply);
      dialog.__lrOutcomeObserver.observe(dialog, { childList: true, subtree: true });
      dialog.addEventListener("input", apply);
      dialog.addEventListener("change", apply);
    }
    apply();
  }

  function wireEvent(dialog) {
    var ear = control(dialog, /Ear Tag\b/, "input");
    if (!ear) return;
    wireVitalEventDate(dialog);
    // Breeding Details is the only event dialog with a "Breeding Type" select
    // (the others all say "Event Type") -- used below to offer only Female
    // animals in the ear-tag dropdown. The server rejects a male tag typed by
    // hand regardless (see G2PRegisterDomainServiceBreeding._validate_female_only) --
    // this dialog cannot filter what it accepts, only what it suggests.
    var femaleOnly = !!control(dialog, /^Breeding Type\b/, "select");
    wireBreedingOutcome(dialog);
    cache.animals = {}; // animals may have been added since the last dialog
    submissionAnimals().then(function (animals) {
      var dropdownAnimals = femaleOnly
        ? animals.filter(function (a) { return String(a.gender || "").toUpperCase() === "FEMALE"; })
        : animals;
      var dl = document.getElementById("lr-ear-tag-suggestions");
      if (!dl) { dl = document.createElement("datalist"); dl.id = "lr-ear-tag-suggestions"; document.body.appendChild(dl); }
      dl.innerHTML = "";
      dropdownAnimals.forEach(function (a) {
        var o = document.createElement("option");
        o.value = a.tag;
        o.label = pretty(a.species, "LIVESTOCK_SPECIES_") + (a.breed ? " / " + pretty(a.breed, "LIVESTOCK_BREED_") : "");
        dl.appendChild(o);
      });
      ear.setAttribute("list", "lr-ear-tag-suggestions");
      ear.setAttribute("autocomplete", "off");
      if (dropdownAnimals.length && !ear.getAttribute("placeholder")) ear.setAttribute("placeholder", "Pick or type an ear tag of this form");

      // a real dropdown of this form's animals + a description line, under the field
      var box = ear.parentElement; while (box && box.parentElement && !/flex-1/.test(box.className)) box = box.parentElement;
      var host = box || ear.parentElement;
      var pick = document.createElement("select"); pick.className = CONTROL_CLASS + " mt-1"; pick.id = "lr-animal-pick";
      var ph = document.createElement("option"); ph.value = "";
      ph.textContent = dropdownAnimals.length ? "Pick an animal of this form\u2026" : (femaleOnly ? "No female animals saved on this form yet" : "No animals saved on this form yet");
      pick.appendChild(ph);
      dropdownAnimals.forEach(function (a) { var o = document.createElement("option"); o.value = a.tag; o.textContent = a.tag + " \u2014 " + describe(a); pick.appendChild(o); });
      var info = infoLine("lr-animal-info");
      host.appendChild(pick); host.appendChild(info);
      var find = function () { var t = String(ear.value || "").trim().toUpperCase(); for (var i = 0; i < animals.length; i++) if (animals[i].tag === t) return animals[i]; return null; };
      keepDisplay(dialog);
      var reflect = function () {
        var a = find(); var t = String(ear.value || "").trim();
        var notFemale = femaleOnly && a && String(a.gender || "").toUpperCase() !== "FEMALE";
        pick.value = a && !notFemale ? a.tag : "";
        setDisplay(dialog, "species", a ? pretty(a.species, "LIVESTOCK_SPECIES_") : "");
        setDisplay(dialog, "age", a ? (a.age || ageFrom(a.dob)) : "");
        if (notFemale) {
          info.textContent = "Not a Female animal \u2014 breeding can only be logged against a Female (this is " + pretty(a.gender, "") + ")";
        } else {
          info.textContent = a ? describeRest(a) : (t ? "Not an animal of this form \u2014 add it under Livestock Details first" : "");
        }
        info.style.color = a && !notFemale || !t ? "" : "#b91c1c";
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
        wireNextDueDate(dialog, vaccine, list);
      });
    });
  }

  // ---- Configuration -> Attribute Values: Species / Interval / Active / Notes ----
  // The portal's Add/Edit Attribute Value dialog only has Value Code and Display
  // Order. The backend already stores parent_value_id (the species), interval_days,
  // is_active and notes, so the extra fields are added here and merged into the
  // portal's own create/update request (see the fetch wrapper above).
  var ATTR_FIELDS = {
    VACCINE_TYPE: { parent: true, schedule: true },
    LIVESTOCK_BREED: { parent: true },
    LIVESTOCK_SPECIES: { speciesConfig: true }
  };
  function wireAttributeValue(dialog) {
    var pathMatch = location.pathname.match(/\/configuration\/attributes\/([^/?#]+)/);
    var attr = pathMatch && decodeURIComponent(pathMatch[1]);
    var cfg = attr && ATTR_FIELDS[attr];
    if (!cfg) return;
    var order = control(dialog, /^Display Order\b/, "input");
    var code = control(dialog, /^Value Code\b/, "input");
    if (!order || !code) return;
    var labels = dialog.querySelectorAll("label"), label = null;
    for (var i = 0; i < labels.length; i++) if (/^Display Order\b/.test(labels[i].textContent.trim())) label = labels[i];
    var anchor = label && label.parentElement;
    if (!anchor || !anchor.parentNode) return;

    var makeBox = function (text, el) {
      var b = anchor.cloneNode(false), l = label.cloneNode(false);
      l.textContent = text; l.removeAttribute("for");
      b.appendChild(l); b.appendChild(el); return b;
    };
    var species = document.createElement("select"); species.className = order.className;
    var interval = document.createElement("input"); interval.type = "number"; interval.min = "1"; interval.step = "1";
    interval.className = order.className; interval.placeholder = "Days between doses, e.g. 180";
    var active = document.createElement("input"); active.type = "checkbox"; active.checked = true;
    var notes = document.createElement("input"); notes.type = "text"; notes.className = order.className;

    // Species-level switches: an animal of a species without an ear tag (poultry, beehive, ...)
    // is registered by Secondary Identifier + Quantity instead — see wireAnimal.
    var needsTag = document.createElement("input"); needsTag.type = "checkbox"; needsTag.checked = true;
    var isFlock = document.createElement("input"); isFlock.type = "checkbox"; isFlock.checked = false;

    var boxes = [];
    if (cfg.parent) boxes.push(makeBox("Species", species));
    if (cfg.speciesConfig) boxes.push(makeBox("Requires Ear Tag", needsTag), makeBox("Flock / Group Species", isFlock));
    if (cfg.schedule) boxes.push(makeBox("Interval (days)", interval), makeBox("Active", active), makeBox("Notes", notes));
    var ref = anchor.nextSibling;
    boxes.forEach(function (b) { anchor.parentNode.insertBefore(b, ref); });

    var blank = document.createElement("option"); blank.value = ""; blank.textContent = "Select species…"; species.appendChild(blank);
    attributeValues("LIVESTOCK_SPECIES").then(function (list) {
      list.forEach(function (v) {
        var o = document.createElement("option"); o.value = v.value_id;
        o.textContent = v.value_display || pretty(v.value_id, "LIVESTOCK_SPECIES_"); species.appendChild(o);
      });
      prefill();
    });

    // Edit: the dialog opens with the row's Value Code already filled in.
    var typed = false, tries = 0, filled = false;
    code.addEventListener("input", function (e) { if (e.isTrusted) typed = true; });
    var prefill = function () {
      if (filled || typed || !code.value.trim() || (cfg.parent && species.options.length < 2)) return;
      attributeValues(attr).then(function (rows) {
        var row = null, c = code.value.trim();
        for (var i = 0; i < rows.length; i++) if (rows[i].value_code === c) { row = rows[i]; break; }
        if (!row || filled) return;
        filled = true;
        species.value = row.parent_value_id || "";
        interval.value = row.interval_days || "";
        active.checked = row.is_active !== false;
        notes.value = row.notes || "";
        needsTag.checked = row.requires_ear_tag !== false;
        isFlock.checked = row.is_flock_species === true;
      });
    };
    var timer = setInterval(function () {
      if (!document.body.contains(dialog) || ++tries > 25) { clearInterval(timer); return; }
      prefill();
    }, 150);

    attrExtra = {
      dialog: dialog,
      read: function () {
        var out = {};
        if (cfg.parent && species.value) out.parent_value_id = species.value;
        if (cfg.speciesConfig) {
          out.requires_ear_tag = needsTag.checked;
          out.is_flock_species = isFlock.checked;
        }
        if (cfg.schedule) {
          var n = parseInt(interval.value, 10);
          if (n > 0) out.interval_days = n;
          out.is_active = active.checked;
          if (notes.value.trim()) out.notes = notes.value.trim();
        }
        return out;
      }
    };
  }

  // ---- Intake form -> Farmer section: Registration Date starts as today ------
  // The platform's "today" default does not fill a date picker that sits on the
  // page (only the server resolves it on save), so a new form is filled here
  // once. Only /new/ forms: a reopened draft keeps whatever was saved. The
  // Livestock Details dialog has a Registration Date of its own; dialogs are
  // skipped here.
  var farmerDateDone = new WeakSet();
  function wireFarmerRegistrationDate() {
    if (!/\/intake-form\/[^/]+\/new\//.test(location.pathname)) return;
    var labels = document.querySelectorAll("label");
    for (var i = 0; i < labels.length; i++) {
      if (!/^Registration Date\b/.test(labels[i].textContent.replace(/\s+/g, " ").trim())) continue;
      if (labels[i].closest(DIALOG)) continue;
      var input = labels[i].parentElement && labels[i].parentElement.querySelector("input");
      if (!input || farmerDateDone.has(input)) continue;
      farmerDateDone.add(input);
      var today = writeDate(input, new Date());
      if (input.type === "date") input.max = today;
      if (!input.value) setValue(input, today);
    }
  }

  // ---- watch for dialogs -----------------------------------------------------
  var wired = new WeakSet();
  function scan() {
    try { wireFarmerRegistrationDate(); } catch (e) { /* never break the form */ }
    var dialogs = document.querySelectorAll(DIALOG);
    for (var i = 0; i < dialogs.length; i++) {
      var d = dialogs[i];
      if (wired.has(d)) continue;
      if (!d.querySelector("label")) continue; // not rendered yet
      wired.add(d);
      try {
        if (control(d, /^Breed\b/, "select")) wireAnimal(d);
        else if (control(d, /Ear Tag\b/, "input")) wireEvent(d);
        else if (control(d, /^Value Code\b/, "input")) wireAttributeValue(d);
      } catch (e) { /* overlay must never break the dialog */ }
    }
  }
  new MutationObserver(scan).observe(document.documentElement, { childList: true, subtree: true });
  scan();
})();
