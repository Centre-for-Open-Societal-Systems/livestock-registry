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
 *   - Event dialogs (Health / Vaccination / Vital / Breeding): the Ear Tag
 *     field becomes a dropdown of this submission's animals (species /
 *     breed / sex / age in each option; the platform's text input stays
 *     hidden behind it as the submitted field, and is shown only when
 *     there is no animal to pick). Choosing one fills the read-only
 *     Species and Age fields (the server fills the same two columns on
 *     save) and two on-screen-only fields, Breed and Sex, added under
 *     Species; on the Vaccination dialog the Vaccine list is narrowed to
 *     that animal's species, and Next Due Date is filled as Vaccination
 *     Date + the vaccine's configured interval.
 *   - Health Status values (tables and read-only views) show as colored
 *     pills: Healthy green, Sick orange, Quarantined red, Deceased grey.
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
  // A registered Livestock record (/register/livestock/<internal id>): its
  // Edit Details dialogs pick animals from the record itself, not a submission.
  var LIVESTOCK_REGISTER = "997676d3-7008-59f9-b23e-613ad79bbb08";
  var ANIMAL_REGISTER = "041a9f79-2142-548a-a15b-a4c76fc9f6f7";
  function registerRecordId() {
    var r = location.pathname.match(/\/register\/livestock\/([^/?#]+)/);
    return r ? decodeURIComponent(r[1]) : null;
  }

  var nativeFetch = window.fetch;
  var attrExtra = null; // set while a Configuration -> Attribute Values dialog carries our extra fields
  // File Import: the upload returns document_id + document_store_id, but the
  // portal enqueues the import with document_store_id only, which the API
  // rejects (it needs document_id). Remember each upload's pair and add the
  // document_id to the enqueue request (patch-enqueue-import-route.js lets
  // the route forward it).
  var uploadedDocIds = {};
  function rememberUploadedDocs(o) {
    if (Array.isArray(o)) { o.forEach(rememberUploadedDocs); return; }
    if (!o || typeof o !== "object") return;
    if (o.document_store_id && o.document_id) uploadedDocIds[o.document_store_id] = o.document_id;
    Object.keys(o).forEach(function (k) { rememberUploadedDocs(o[k]); });
  }

  window.fetch = function (input, init) {
    var args = arguments;
    var isAttrSave = false;
    try {
      var reqUrl = typeof input === "string" ? input : (input && input.url) || "";
      if (reqUrl.indexOf("/api/input-mechanism/enqueue-import") > -1 && init && typeof init.body === "string") {
        var enq = JSON.parse(init.body);
        if (!enq.document_id && enq.document_store_id && uploadedDocIds[enq.document_store_id]) {
          enq.document_id = uploadedDocIds[enq.document_store_id];
          args = [input, Object.assign({}, init, { body: JSON.stringify(enq) })];
        }
      }
    } catch (e) { /* never break the portal */ }
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
      if (/upload-document/.test(typeof input === "string" ? input : (input && input.url) || "")) {
        p.then(function (res) {
          if (res && res.ok) res.clone().json().then(rememberUploadedDocs).catch(function () {});
        }).catch(function () {});
      }
    } catch (e) { /* never break the portal */ }
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
    if (!id) return recordAnimals();
    if (!cache.animals[id]) {
      cache.animals[id] = post("/api/intake-form/get-intake-form-submission", { submission_id: id })
        .then(extractAnimals).catch(function () { return []; });
    }
    return cache.animals[id];
  }
  function recordAnimals() {
    var id = registerRecordId();
    if (!id) return Promise.resolve([]);
    var key = "record:" + id;
    if (!cache.animals[key]) {
      cache.animals[key] = post("/api/register/section-data", {
        register_id: LIVESTOCK_REGISTER, internal_record_id: id, section_register_id: ANIMAL_REGISTER
      }).then(extractAnimals).catch(function () { return []; });
    }
    return cache.animals[key];
  }
  function extractAnimals(json) {
    var out = [], seen = {};
    (function walk(o) {
      if (Array.isArray(o)) { o.forEach(walk); return; }
      if (!o || typeof o !== "object") return;
      // an animal row: has breed + an identifier, and is not an event row.
      // The identifier is the ear tag or, for a species with no ear to tag
      // (poultry, beehives), the secondary identifier -- whichever the
      // Livestock Details dialog collected. Event rows name the animal by
      // that same value in ear_tag_id, and the server accepts either
      // (animal_identified_by in domain_validation_utils). Ear tags are
      // upper-cased like the server stores them; a secondary identifier is
      // free text and is kept exactly as typed, since the server matches it
      // exactly -- `key` is the case-folded form used only for matching here.
      if (("breed" in o) && !("event_type" in o) && !("vaccine_type" in o) && (o.ear_tag_id || o.secondary_identifier)) {
        var tag = o.ear_tag_id ? String(o.ear_tag_id).trim().toUpperCase() : String(o.secondary_identifier).trim();
        var key = tag.toUpperCase();
        if (tag && !seen[key]) {
          seen[key] = true;
          out.push({ tag: tag, key: key, earTag: !!o.ear_tag_id, species: o.species || "", breed: o.breed || "", gender: o.gender || "", dob: o.date_of_birth || "", age: o.age || "", quantity: o.quantity || "", health: o.health_status || "" });
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
  function describe(a) {
    var parts = [pretty(a.species, "LIVESTOCK_SPECIES_")];
    if (a.breed) parts.push(pretty(a.breed, "LIVESTOCK_BREED_"));
    if (a.gender) parts.push(pretty(a.gender, ""));
    var age = a.age || ageFrom(a.dob); if (age) parts.push("age " + age);
    if (a.quantity) parts.push(a.quantity + " head");
    return parts.join(" \u00b7 ");
  }
  var CONTROL_CLASS = "w-full sm:w-[180px] max-w-full h-[30px] px-3 border shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white";
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
      // Registration Date cannot be before Date of Birth (the server checks
      // too: G2PRegisterDomainServiceAnimal._validate_registration_not_before_birth).
      if (!problem) {
        var dobNow = control(dialog, /^Date of Birth\b/, "input"), regNow = control(dialog, /^Registration Date\b/, "input");
        var born = dobNow ? readDate(dobNow) : null, registered = regNow ? readDate(regNow) : null;
        if (born && registered && registered < born) {
          problem = "Registration date cannot be before the animal's date of birth (" +
            pad2(born.getDate()) + "/" + pad2(born.getMonth() + 1) + "/" + born.getFullYear() + ").";
        }
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
    // Only a Female can be bred or give birth, so the ear-tag dropdown offers
    // only Female animals on Breeding Details (the only event dialog with a
    // "Breeding Type" select) and on Vital Event Details while its Event Type
    // is BIRTH -- re-evaluated whenever Event Type changes. The server rejects
    // a male tag typed by hand regardless (_validate_female_only on Breeding,
    // _validate_birth_female_only on Vital Event) -- this dialog cannot filter
    // what it accepts, only what it suggests.
    var isBreeding = !!control(dialog, /^Breeding Type\b/, "select");
    // Ear Tag Replacement: the Old Ear Tag picker offers only living animals
    // that carry an ear tag -- a secondary identifier has no tag to replace and
    // a deceased animal cannot be retagged (both refused on approval too).
    var isRetag = !!control(dialog, /^New Ear Tag\b/, "input");
    var femaleOnly = function () {
      if (isBreeding) return true;
      var eventType = control(dialog, /^Event Type\b/, "select");
      return !!eventType && String(eventType.value || "").toUpperCase() === "BIRTH";
    };
    var femaleReason = function () {
      return isBreeding ? "breeding can only be logged against a Female" : "a birth can only be logged against a Female";
    };
    wireBreedingOutcome(dialog);
    cache.animals = {}; // animals may have been added since the last dialog
    submissionAnimals().then(function (animals) {
      var dropdownAnimals = [];
      // One control for the ear tag. The platform's text input stays the field
      // the form validates and submits, but it is hidden and a dropdown of this
      // form's animals stands in its place: the server only accepts an animal
      // of this very submission anyway (ensure_ear_tags_belong_to_submission),
      // so there is nothing a typed tag could add but a typo. Each option
      // carries the animal's species / breed / sex / age, so no extra
      // description line is needed under the field. The text input is left
      // visible only when there is nothing to pick from (no animal saved yet,
      // or the submission lookup failed), so a tag can still be typed then.
      var pick = document.createElement("select"); pick.className = ear.className; pick.id = "lr-animal-pick";
      var filteredFor = null; // femaleOnly() the options were last built for
      var buildOptions = function () {
        var female = femaleOnly();
        if (filteredFor === female) return false;
        filteredFor = female;
        dropdownAnimals = female
          ? animals.filter(function (a) { return String(a.gender || "").toUpperCase() === "FEMALE"; })
          : animals;
        if (isRetag) {
          dropdownAnimals = dropdownAnimals.filter(function (a) {
            return a.earTag && String(a.health || "").toUpperCase() !== "DECEASED";
          });
        }
        while (pick.options.length) pick.remove(0);
        var ph = document.createElement("option"); ph.value = "";
        ph.textContent = dropdownAnimals.length ? "Select an animal of this form\u2026" : (female ? "No female animals saved on this form yet" : "No animals saved on this form yet");
        pick.appendChild(ph);
        dropdownAnimals.forEach(function (a) { var o = document.createElement("option"); o.value = a.tag; o.textContent = a.tag + " \u2014 " + describe(a); pick.appendChild(o); });
        return true;
      };
      buildOptions();
      var find = function () { var t = String(ear.value || "").trim().toUpperCase(); for (var i = 0; i < animals.length; i++) if (animals[i].key === t) return animals[i]; return null; };
      // Breed and Sex of the picked animal, shown as two more read-only fields
      // in the row under Species (Species and Age are the platform's own
      // display widgets from the metadata; these two are clones of the
      // Species cell, so they look the same and setDisplay fills them the
      // same way). Purely on screen: the event row has no breed/sex columns.
      var EXTRA = [["breed", "Breed"], ["gender", "Sex"]];
      var extras = function () {
        var speciesBox = dialog.querySelector('.widget-container[data-widget-id$="-species"]');
        if (!speciesBox || !speciesBox.parentElement) return;
        var after = speciesBox.parentElement; // the grid cell holding the widget
        EXTRA.forEach(function (pair) {
          var key = pair[0], label = pair[1];
          var have = dialog.querySelector('.widget-container[data-widget-id="lr-extra-' + key + '"]');
          if (have) { after = have.parentElement; return; }
          var cell = after.cloneNode(true);
          var box = cell.querySelector(".widget-container") || cell;
          box.setAttribute("data-widget-id", "lr-extra-" + key);
          var lab = box.querySelector("[title]"); if (lab) { lab.textContent = label + ":"; lab.title = label; }
          var val = box.querySelector(".flex-1 > div"); if (val) { val.textContent = "-"; val.title = "-"; }
          after.insertAdjacentElement("afterend", cell);
          after = cell;
        });
      };
      var place = function () {
        // (re)attach after every dialog re-render: the platform may remount the input
        var current = control(dialog, /Ear Tag\b/, "input");
        if (current && current !== ear) { ear = current; }
        if (!ear) return;
        if (pick.parentElement !== ear.parentElement) ear.insertAdjacentElement("afterend", pick);
        var hide = dropdownAnimals.length > 0;
        if ((ear.style.display === "none") !== hide) ear.style.display = hide ? "none" : "";
        extras();
      };
      keepDisplay(dialog);
      var hasOption = function (value) {
        // by value, not a CSS selector: an ear tag is free text until the
        // server has seen it, and a quote or bracket in it would make
        // querySelector throw out of reflect() and freeze the whole dialog.
        for (var i = 0; i < pick.options.length; i++) if (pick.options[i].value === value) return true;
        return false;
      };
      var extraApply = null; // set below by the Vaccination dialog's own wiring
      var reflect = function () {
        var a = find(); var t = a ? a.tag : String(ear.value || "").trim();
        // A tag the dropdown does not offer: an Edit of a row whose animal has
        // since left the form, or (on Breeding) one of this form's animals that
        // the Female-only filter left out. Add it as an option either way, so
        // the field shows what is actually saved instead of the placeholder,
        // and say why it is not a normal choice.
        if (t && !hasOption(t)) {
          var o = document.createElement("option"); o.value = t;
          o.textContent = a
            ? t + " \u2014 " + describe(a) + (filteredFor ? " \u2014 not a Female, " + femaleReason() : "")
            : t + " \u2014 not an animal of this form";
          pick.appendChild(o);
        }
        if (pick.value !== t) pick.value = t;
        setDisplay(dialog, "species", a ? pretty(a.species, "LIVESTOCK_SPECIES_") : "");
        setDisplay(dialog, "age", a ? (a.age || ageFrom(a.dob)) : "");
        setDisplay(dialog, "breed", a && a.breed ? pretty(a.breed, "LIVESTOCK_BREED_") : "");
        setDisplay(dialog, "gender", a && a.gender ? pretty(a.gender, "") : "");
        if (extraApply) extraApply();
      };
      pick.addEventListener("change", function () { setValue(ear, pick.value); reflect(); });
      dialog.addEventListener("input", function (e) { if (e.target === ear) reflect(); });
      dialog.addEventListener("change", function (e) {
        if (e.target === ear) reflect();
        // Event Type switched to/from BIRTH: rebuild the list for the new filter
        else if (e.target === control(dialog, /^Event Type\b/, "select") && buildOptions()) { place(); reflect(); }
      });
      if (!dialog.__lrPickObserver) {
        dialog.__lrPickObserver = new MutationObserver(function () { place(); reflect(); });
        dialog.__lrPickObserver.observe(dialog, { childList: true, subtree: true });
      }
      place(); reflect();

      var vaccine = control(dialog, /^Vaccine\b/, "select");
      if (!vaccine) return;
      attributeValues(VACCINE_ATTR).then(function (list) {
        var map = byParent(list);
        var apply = function () {
          var tag = String(ear.value || "").trim().toUpperCase();
          var a = null;
          for (var i = 0; i < animals.length; i++) if (animals[i].key === tag) { a = animals[i]; break; }
          restrictOptions(vaccine, a && a.species ? (map[a.species] || {}) : null);
        };
        // Driven from reflect(), not from listeners on `ear`: place() swaps
        // `ear` for the new node whenever the platform remounts the field, and
        // listeners bound to the old node would stop firing with it.
        extraApply = apply;
        observeOptions(vaccine, apply);
        apply();
        wireNextDueDate(dialog, vaccine, list);
      });

      // Vaccination Date cannot be before the picked animal's Date of Birth.
      // Checked on Save, with the reason shown above the buttons; the server
      // checks the same rule (G2PRegisterDomainServiceVaccination
      // ._validate_not_before_birth). No Date of Birth on file = no check.
      var save = null, buttons = dialog.querySelectorAll("button");
      for (var b = 0; b < buttons.length; b++) if (/^Save\b/.test(buttons[b].textContent.trim())) save = buttons[b];
      if (!save) return;
      var msg = document.createElement("div"); msg.className = "text-sm mt-2"; msg.style.color = "#b91c1c"; msg.style.minHeight = "1.25rem";
      if (save.parentElement && save.parentElement.parentElement) save.parentElement.parentElement.insertBefore(msg, save.parentElement);
      save.addEventListener("click", function (e) {
        msg.textContent = "";
        var a = find(), vacDate = control(dialog, /^Vaccination Date\b/, "input");
        if (!a || !a.dob || !vacDate) return;
        var dob = new Date(String(a.dob).slice(0, 10) + "T00:00:00"), when = readDate(vacDate);
        if (isNaN(dob.getTime()) || !when || when >= dob) return;
        e.preventDefault(); e.stopImmediatePropagation();
        msg.textContent = "Vaccination date cannot be before the animal's date of birth (" +
          pad2(dob.getDate()) + "/" + pad2(dob.getMonth() + 1) + "/" + dob.getFullYear() + ").";
      }, true);
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

  // ---- Health Status: colored pill wherever the value is displayed -----------
  // The section schema carries "widget-badge-colors" for health_status, but the
  // published staff-ui ignores that key, so the value renders as plain text.
  // Standardized colors (Healthy green, Ill orange, Quarantined red; Deceased,
  // which the standard does not cover, neutral grey) are painted here instead,
  // only on values under a "Health Status" table column or next to a
  // "Health Status" label, so the same words elsewhere are left alone.
  var HEALTH_BADGE = {
    HEALTHY: ["#DCFCE7", "#166534"],
    SICK: ["#FFEDD5", "#9A3412"],
    QUARANTINED: ["#FEE2E2", "#991B1B"],
    DECEASED: ["#E5E7EB", "#374151"]
  };
  var HEALTH_LABEL = /^Health Status\s*\*?:?$/i;
  var painted = new Set();

  function healthCode(el) {
    var t = String(el.textContent || "").trim().toUpperCase();
    return HEALTH_BADGE.hasOwnProperty(t) ? t : null;
  }
  function badgeTarget(box) {
    // the innermost element holding the value; the box itself if it only has text
    var leaf = box;
    while (leaf.children.length === 1 && healthCode(leaf.children[0])) leaf = leaf.children[0];
    return leaf;
  }
  function paintBadge(el, code) {
    if (el.__lrHealth === code) return;
    var c = HEALTH_BADGE[code], isCell = /^T[DH]$/.test(el.tagName);
    el.style.backgroundColor = c[0];
    el.style.color = c[1];
    el.style.fontWeight = "600";
    if (!isCell) {
      el.style.display = "inline-block";
      el.style.padding = "2px 10px";
      el.style.borderRadius = "9999px";
    }
    el.__lrHealth = code;
    painted.add(el);
  }
  function clearBadge(el) {
    ["backgroundColor", "color", "fontWeight", "display", "padding", "borderRadius"].forEach(function (p) { el.style[p] = ""; });
    el.__lrHealth = null;
    painted.delete(el);
  }
  function paintHealthStatus() {
    var seen = new Set();
    var mark = function (box) {
      if (!box) return;
      var target = badgeTarget(box), code = healthCode(target);
      if (!code) return;
      paintBadge(target, code);
      seen.add(target);
    };
    // table columns headed "Health Status"
    var heads = document.querySelectorAll("th");
    for (var i = 0; i < heads.length; i++) {
      if (!HEALTH_LABEL.test(heads[i].textContent.replace(/\s+/g, " ").trim())) continue;
      var table = heads[i].closest("table"), idx = heads[i].cellIndex;
      if (!table || idx < 0) continue;
      var rows = table.tBodies.length ? table.tBodies[0].rows : [];
      for (var r = 0; r < rows.length; r++) mark(rows[r].cells[idx]);
    }
    // read-only "Health Status: VALUE" pairs (the value is the label's next sibling)
    var labels = document.querySelectorAll("label, dt, span, p, div");
    for (var j = 0; j < labels.length; j++) {
      var l = labels[j];
      if (l.children.length || l.closest("th") || !HEALTH_LABEL.test(l.textContent.trim())) continue;
      var value = l.nextElementSibling;
      if (value && !value.querySelector("select, input")) mark(value);
    }
    // an element whose value changed away from a status (React reused it)
    painted.forEach(function (el) { if (!seen.has(el) || !document.body.contains(el)) clearBadge(el); });
  }
  var paintQueued = false;
  new MutationObserver(function () {
    if (paintQueued) return;
    paintQueued = true;
    requestAnimationFrame(function () {
      paintQueued = false;
      try { paintHealthStatus(); } catch (e) { /* cosmetic only */ }
    });
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  // ---- Header "Animals" button: country-wide animal list + bulk status update ----
  // SRS LR-24. The portal has no page listing every animal (Animal is a child
  // table of each Livestock record), so this opens a full-screen panel over
  // the current page. The list comes from the platform's own register search
  // on the Animal register (/api/register/records); a bulk update is sent as
  // ordinary change requests (/api/change-request/create) -- one per
  // Livestock record, holding the selected animals' rows with only the
  // status changed -- so it goes through the normal approval, history and
  // before/after audit log like any single edit.
  var ANIMAL_TAB = "livestock_animal_tab", ANIMAL_SECTION = "livestock_animal_details_section_01";
  var HEALTH_CHOICES = [["HEALTHY", "Healthy"], ["SICK", "Sick"], ["QUARANTINED", "Quarantined"]];
  var VACC_CHOICES = [["UP_TO_DATE", "Up-to-date"], ["OVERDUE", "Overdue"], ["NONE", "None"]];

  function csrfToken() {
    var m2 = document.cookie.match(/(?:^|;\s*)X-CSRF-Token=([^;]+)/);
    return m2 ? decodeURIComponent(m2[1]) : "";
  }
  function postJson(path, body) {
    var headers = { "content-type": "application/json" }, t = csrfToken();
    if (t) headers["X-CSRF-Token"] = t;
    return nativeFetch(path, { method: "POST", credentials: "same-origin", headers: headers, body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, json: j }; }); });
  }
  function el(tag, style, text) {
    var e = document.createElement(tag);
    if (style) e.style.cssText = style;
    if (text != null) e.textContent = text;
    return e;
  }
  function selectOf(options, first) {
    var s = el("select", "border:1px solid #cbd5e1;border-radius:6px;padding:6px 8px;background:#fff;font-size:14px");
    s.appendChild(new Option(first, ""));
    options.forEach(function (o) { s.appendChild(new Option(o[1], o[0])); });
    return s;
  }
  var BTN = "background:#15803d;color:#fff;border:0;border-radius:6px;padding:7px 14px;font-size:14px;cursor:pointer";
  var BTN_LIGHT = "background:#fff;color:#15803d;border:1px solid #15803d;border-radius:6px;padding:6px 12px;font-size:14px;cursor:pointer";

  function openAnimalsPanel() {
    if (document.getElementById("lr-animals-panel")) return;
    var state = { page: 1, pages: 1, total: 0, rows: [], selected: {} };
    var shade = el("div", "position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9990;display:flex;align-items:center;justify-content:center");
    shade.id = "lr-animals-panel";
    var card = el("div", "background:#fff;border-radius:10px;width:min(1200px,96vw);height:90vh;display:flex;flex-direction:column;padding:18px 20px;box-shadow:0 10px 30px rgba(0,0,0,.25);font-family:inherit;color:#111827");
    shade.appendChild(card);
    var head = el("div", "display:flex;justify-content:space-between;align-items:center;margin-bottom:12px");
    head.appendChild(el("div", "font-size:20px;font-weight:600", "Animals — all registered animals"));
    var close = el("button", "background:none;border:0;font-size:26px;cursor:pointer;line-height:1", "×");
    close.title = "Close";
    close.onclick = function () { shade.remove(); };
    head.appendChild(close);
    card.appendChild(head);

    // filters
    var filters = el("div", "display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px");
    var search = el("input", "border:1px solid #cbd5e1;border-radius:6px;padding:6px 10px;font-size:14px;min-width:220px");
    search.placeholder = "Search ear tag / identifier";
    var species = selectOf([], "All species");
    var health = selectOf(HEALTH_CHOICES.concat([["DECEASED", "Deceased"]]), "All health statuses");
    var vacc = selectOf(VACC_CHOICES, "All vaccination statuses");
    var go = el("button", BTN, "Search");
    [search, species, health, vacc, go].forEach(function (x) { filters.appendChild(x); });
    card.appendChild(filters);
    attributeValues("LIVESTOCK_SPECIES").then(function (list) {
      list.forEach(function (v) { if (v && v.value_id) species.appendChild(new Option(v.value_display || v.value_id, v.value_id)); });
    });

    // bulk bar
    var bar = el("div", "display:flex;gap:8px;flex-wrap:wrap;align-items:center;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:8px 10px;margin-bottom:10px");
    var selInfo = el("span", "font-weight:600;margin-right:6px", "0 selected");
    var setHealth = selectOf(HEALTH_CHOICES, "Health Status: no change");
    var setVacc = selectOf(VACC_CHOICES, "Vaccination Status: no change");
    var apply = el("button", BTN, "Apply to selected");
    var clearSel = el("button", BTN_LIGHT, "Clear selection");
    [selInfo, setHealth, setVacc, apply, clearSel].forEach(function (x) { bar.appendChild(x); });
    card.appendChild(bar);
    var msg = el("div", "min-height:20px;font-size:14px;margin-bottom:6px;white-space:pre-line");
    card.appendChild(msg);

    // table
    var wrap = el("div", "flex:1;overflow:auto;border:1px solid #e5e7eb;border-radius:8px");
    var table = el("table", "width:100%;border-collapse:collapse;font-size:14px");
    var thead = el("thead", "position:sticky;top:0;background:#f9fafb");
    var hr = el("tr");
    var allBox = el("input"); allBox.type = "checkbox"; allBox.title = "Select all on this page";
    var th0 = el("th", "padding:8px;text-align:left;border-bottom:1px solid #e5e7eb;width:36px"); th0.appendChild(allBox); hr.appendChild(th0);
    ["Ear Tag / Identifier", "Species", "Breed", "Sex", "Health Status", "Vaccination Status", "Livestock Record"].forEach(function (h) {
      hr.appendChild(el("th", "padding:8px;text-align:left;border-bottom:1px solid #e5e7eb;font-weight:600;color:#374151", h));
    });
    thead.appendChild(hr); table.appendChild(thead);
    var tbody = el("tbody"); table.appendChild(tbody);
    wrap.appendChild(table); card.appendChild(wrap);

    var pager = el("div", "display:flex;justify-content:flex-end;align-items:center;gap:10px;margin-top:10px");
    var prev = el("button", BTN_LIGHT, "← Previous"), next = el("button", BTN_LIGHT, "Next →"), pinfo = el("span");
    [pinfo, prev, next].forEach(function (x) { pager.appendChild(x); });
    card.appendChild(pager);
    document.body.appendChild(shade);

    function selectedCount() { return Object.keys(state.selected).length; }
    function refreshSel() {
      selInfo.textContent = selectedCount() + " selected";
      allBox.checked = state.rows.length > 0 && state.rows.every(function (r) { return state.selected[r.id]; });
    }
    function badge(code) {
      var c = (typeof HEALTH_BADGE !== "undefined" && HEALTH_BADGE[code]) || null, s = el("span", "", code || "-");
      if (c) s.style.cssText = "background:" + c[0] + ";color:" + c[1] + ";padding:2px 10px;border-radius:9999px;font-weight:600";
      return s;
    }
    function render() {
      tbody.innerHTML = "";
      if (!state.rows.length) {
        var tr0 = el("tr"), td0 = el("td", "padding:16px;text-align:center;color:#6b7280", "No animals found");
        td0.colSpan = 8; tr0.appendChild(td0); tbody.appendChild(tr0);
      }
      state.rows.forEach(function (r) {
        var tr = el("tr", "border-bottom:1px solid #f3f4f6");
        var cb = el("input"); cb.type = "checkbox"; cb.checked = !!state.selected[r.id];
        cb.onchange = function () { if (cb.checked) state.selected[r.id] = r; else delete state.selected[r.id]; refreshSel(); };
        var td = el("td", "padding:8px"); td.appendChild(cb); tr.appendChild(td);
        [r.tag, pretty(r.species, "LIVESTOCK_SPECIES_"), pretty(r.breed, "LIVESTOCK_BREED_"), pretty(r.gender, "")].forEach(function (v) {
          tr.appendChild(el("td", "padding:8px", v || "-"));
        });
        var th = el("td", "padding:8px"); th.appendChild(badge(r.health)); tr.appendChild(th);
        tr.appendChild(el("td", "padding:8px", pretty(r.vacc, "") || "-"));
        var tl = el("td", "padding:8px"), a = el("a", "color:#15803d;text-decoration:underline", r.link || "-");
        if (r.link) { a.href = "/en/register/livestock/" + encodeURIComponent(r.link) + "?tab=" + ANIMAL_TAB; a.target = "_blank"; }
        tl.appendChild(a); tr.appendChild(tl);
        tbody.appendChild(tr);
      });
      pinfo.textContent = "Page " + state.page + " of " + state.pages + " — " + state.total + " animals";
      prev.disabled = state.page <= 1; next.disabled = state.page >= state.pages;
      refreshSel();
    }
    function load() {
      var f = {};
      if (species.value) f.species = species.value;
      if (health.value) f.health_status = health.value;
      if (vacc.value) f.vaccination_status = vacc.value;
      tbody.innerHTML = "<tr><td colspan='8' style='padding:16px;text-align:center;color:#6b7280'>Loading…</td></tr>";
      postJson("/api/register/records", {
        register_id: ANIMAL_REGISTER, current_page: state.page, page_size: 25,
        search_text: search.value.trim(), filter_by: Object.keys(f).length ? JSON.stringify(f) : ""
      }).then(function (res) {
        var j = res.json || {}, d = j.records ? j : (j.data || j);
        var recs = d.records || [], pg = d.pagination || {};
        state.rows = recs.map(function (rec) {
          var df = {};
          (rec.display_fields || []).forEach(function (x) { df[x.field_name] = x.value; });
          return { id: rec.internal_record_id, link: rec.link_internal_record_id, tag: df.ear_tag_id || df.secondary_identifier,
                   species: df.species, breed: df.breed, gender: df.gender, health: df.health_status, vacc: df.vaccination_status };
        });
        state.total = pg.number_of_items || state.rows.length;
        state.pages = Math.max(1, pg.number_of_pages || 1);
        render();
      }).catch(function () { msg.style.color = "#b91c1c"; msg.textContent = "Could not load animals."; });
    }
    go.onclick = function () { state.page = 1; load(); };
    search.onkeydown = function (e) { if (e.key === "Enter") { state.page = 1; load(); } };
    prev.onclick = function () { if (state.page > 1) { state.page--; load(); } };
    next.onclick = function () { if (state.page < state.pages) { state.page++; load(); } };
    allBox.onchange = function () {
      state.rows.forEach(function (r) { if (allBox.checked) state.selected[r.id] = r; else delete state.selected[r.id]; });
      render();
    };
    clearSel.onclick = function () { state.selected = {}; render(); };

    apply.onclick = function () {
      var picked = Object.keys(state.selected).map(function (k) { return state.selected[k]; });
      if (!picked.length) { msg.style.color = "#b91c1c"; msg.textContent = "Select at least one animal."; return; }
      if (!setHealth.value && !setVacc.value) { msg.style.color = "#b91c1c"; msg.textContent = "Choose a Health Status and/or Vaccination Status to set."; return; }
      var what = [];
      if (setHealth.value) what.push("Health Status → " + setHealth.options[setHealth.selectedIndex].text);
      if (setVacc.value) what.push("Vaccination Status → " + setVacc.options[setVacc.selectedIndex].text);
      if (!window.confirm("Update " + picked.length + " animal(s)?\n\n" + what.join("\n") +
          "\n\nDeceased animals are skipped. The changes are sent for approval and apply once approved.")) return;
      apply.disabled = true; msg.style.color = "#374151"; msg.textContent = "Submitting…";
      var groups = {};
      picked.forEach(function (r) { (groups[r.link] = groups[r.link] || []).push(r.id); });
      var done = 0, animals = 0, skipped = 0, failed = [];
      var KEEP = ["internal_record_id", "link_internal_record_id", "ear_tag_id", "secondary_identifier", "species", "breed", "gender",
                  "date_of_birth", "registration_date", "quantity", "weight", "colour", "health_status", "vaccination_status"];
      var links = Object.keys(groups);
      (function nextGroup(i) {
        if (i >= links.length) {
          apply.disabled = false;
          msg.style.color = failed.length ? "#b91c1c" : "#166534";
          msg.textContent = "Sent for approval: " + animals + " animal(s) in " + done + " change request(s)." +
            (skipped ? "\nSkipped " + skipped + " deceased animal(s)." : "") +
            (failed.length ? "\nFailed: " + failed.join("; ") : "") +
            "\nApprove them under the Livestock record's Change Request panel.";
          state.selected = {}; load();
          return;
        }
        var link = links[i], wanted = {};
        groups[link].forEach(function (id) { wanted[id] = true; });
        // full rows of this record's animals, so each change row carries every
        // field the Animal section validates, with only the status changed
        postJson("/api/register/section-data", { register_id: LIVESTOCK_REGISTER, internal_record_id: link, section_register_id: ANIMAL_REGISTER })
          .then(function (res) {
            var rows = [];
            (function walk(o) {
              if (Array.isArray(o)) { o.forEach(walk); return; }
              if (!o || typeof o !== "object") return;
              if (o.internal_record_id && wanted[o.internal_record_id] && ("health_status" in o)) { rows.push(o); delete wanted[o.internal_record_id]; }
              Object.keys(o).forEach(function (k) { walk(o[k]); });
            })(res.json);
            var changes = [];
            rows.forEach(function (row) {
              if (String(row.health_status || "").toUpperCase() === "DECEASED") { skipped++; return; }
              var c = { edit_action: "UPDATE" };
              KEEP.forEach(function (k) { if (k in row) c[k] = row[k]; });
              c.link_internal_record_id = c.link_internal_record_id || link;
              if (setHealth.value) c.health_status = setHealth.value;
              if (setVacc.value) c.vaccination_status = setVacc.value;
              changes.push(c);
            });
            if (!changes.length) return null;
            return postJson("/api/change-request/create", {
              register_id: LIVESTOCK_REGISTER, register_mnemonic: "Livestock", section_register_id: ANIMAL_REGISTER,
              tab_id: ANIMAL_TAB, section_id: ANIMAL_SECTION, internal_record_id: link, section_records: changes
            }).then(function (cr) {
              var j = cr.json || {}, h = j.response_header || (j.data && j.data.response_header) || {};
              if (!cr.ok || h.response_status === "ERROR" || j.error) {
                failed.push(link + ": " + (h.response_error_message || j.error || j.message || "request failed"));
              } else { done++; animals += changes.length; }
            });
          })
          .catch(function (e) { failed.push(link + ": " + (e && e.message || "request failed")); })
          .then(function () { nextGroup(i + 1); });
      })(0);
    };

    load();
  }

  function injectAnimalsButton() {
    if (document.getElementById("lr-animals-btn")) return;
    var candidates = document.querySelectorAll("header a, header button, nav a, nav button, a, button");
    var dash = null;
    for (var i = 0; i < candidates.length; i++) {
      var t = (candidates[i].textContent || "").replace(/\s+/g, " ").trim();
      if (t === "Dashboard" && !candidates[i].closest(DIALOG)) { dash = candidates[i]; break; }
    }
    if (!dash || !dash.parentElement) return;
    var btn = dash.cloneNode(true);
    btn.id = "lr-animals-btn";
    btn.removeAttribute("href");
    btn.title = "All registered animals — search and bulk update";
    btn.style.cursor = "pointer";
    var spans = btn.querySelectorAll("span");
    var label = spans.length ? spans[spans.length - 1] : btn;
    if (label === btn) btn.textContent = "Animals"; else label.textContent = "Animals";
    btn.onclick = function (e) { e.preventDefault(); e.stopPropagation(); openAnimalsPanel(); };
    dash.insertAdjacentElement("afterend", btn);
  }
  new MutationObserver(function () {
    try { injectAnimalsButton(); } catch (e) { /* cosmetic only */ }
  }).observe(document.documentElement, { childList: true, subtree: true });

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
