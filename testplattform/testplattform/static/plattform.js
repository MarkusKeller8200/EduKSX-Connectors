/* Testplattform EduKSX-Connectors (#41, #43). Alles über die Plattform (/api/…): API-Keys bleiben auf dem Server.
   Texte aus Beschreibungen und Antworten nur über textContent (kein innerHTML mit Daten). */
"use strict";

const $ = (id) => document.getElementById(id);
const store = {
  get: (k) => { try { return sessionStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { v == null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch { /* ohne Speicher */ } },
};
const zustand = { plugins: [], manifeste: {}, werte: {} };  // werte: zuletzt gesehene IDs je Plugin (für Pfadparameter)

function el(tag, attrs = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kinder.flat(3)) if (k != null && k !== false) e.append(k instanceof Node ? k : String(k));
  return e;
}

function fuelle(ziel, ...kinder) {
  ziel.replaceChildren(...kinder.flat(3).filter((k) => k != null && k !== false));
}

async function plattform(pfad, opt = {}) {
  const h = new Headers(opt.headers || {});
  const t = store.get("tp-token"); if (t) h.set("X-Testplattform-Token", t);
  const r = await fetch(pfad, { ...opt, headers: h });
  if (r.status === 401 && (await r.clone().text()).includes("TESTPLATTFORM_TOKEN")) { await tokenFragen(); return plattform(pfad, opt); }
  return r;
}
async function json(pfad) {
  const r = await plattform(pfad);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || j.meldung || `HTTP ${r.status}`);
  return j;
}
function tokenFragen() {
  return new Promise((ok) => {
    const d = $("d-token");
    d.addEventListener("close", () => { store.set("tp-token", $("token").value); ok(); }, { once: true });
    d.showModal();
  });
}
function bestaetigen(text) {
  return new Promise((ok) => {
    const d = $("d-bestaetigen"); $("d-text").textContent = text;
    d.addEventListener("close", () => ok(d.returnValue === "ja"), { once: true });
    d.returnValue = ""; d.showModal();
  });
}

// ----------------------------------------------------------------------------------------- Ansichten
async function start() {
  const main = $("inhalt");
  fuelle(main, el("p", { "aria-live": "polite", text: "Lade Plugins …" }));
  try { zustand.plugins = await json("/api/plugins"); } catch (e) { fuelle(main, el("p", { class: "fehler", text: e.message })); return; }
  navigation();
  fuelle(main, 
    el("h2", { text: "Eingebundene APIs" }),
    el("p", { class: "leise", text: "Jede API unter apis/ ist ein Plugin. Die Testseite entsteht aus ihrer Beschreibung (GET /plugin.json bzw. /openapi.json)." }),
    el("div", { class: "karten" }, zustand.plugins.map(karte)));
}
function statusPill(p) {
  if (!p.erreichbar) return el("span", { class: "pill err", text: "nicht erreichbar" });
  if (p.status_code === 401) {
    const d = String(p.status?.detail || "");
    if (p.sitzung && !d.includes("API-Key")) return el("span", { class: "pill gelb", text: "erreichbar, nicht angemeldet" });
    return el("span", { class: "pill err", text: "API-Key falsch oder fehlt" });
  }
  const s = p.status || {};
  if (s.konfiguriert === false || s.eingerichtet === false) return el("span", { class: "pill gelb", text: "erreichbar, nicht eingerichtet" });
  if (p.status_code && p.status_code >= 400) return el("span", { class: "pill gelb", text: `erreichbar (Status ${p.status_code})` });
  return el("span", { class: "pill ok", text: "erreichbar" });
}
function karte(p) {
  return el("article", { class: "karte" },
    el("h2", {}, el("a", { href: `#/plugin/${p.name}`, text: p.titel }), " ", el("span", { class: "pill", text: p.version })),
    el("p", {}, statusPill(p)),
    p.beschreibung ? el("p", { text: p.beschreibung }) : null,
    el("dl", { class: "kurz" },
      el("dt", { text: "Adresse" }), el("dd", { class: "pfad", text: p.base_url }),
      el("dt", { text: "API-Key" }), el("dd", { text: p.api_key_gesetzt ? "hinterlegt (auf dem Server)" : "keiner hinterlegt" }),
      p.status?.version ? [el("dt", { text: "Version laut API" }), el("dd", { text: p.status.version })] : null),
    el("a", { href: `#/plugin/${p.name}`, text: `Testseite ${p.titel} öffnen` }));
}
function navigation() {
  fuelle($("hauptnav"), ...zustand.plugins.map((p) => el("a", { href: `#/plugin/${p.name}`, text: p.titel })));
}

async function pluginSeite(name, endpunktId) {
  const main = $("inhalt");
  if (!zustand.plugins.length) { try { zustand.plugins = await json("/api/plugins"); navigation(); } catch { /* weiter */ } }
  let daten = zustand.manifeste[name];
  if (!daten) {
    fuelle(main, el("p", { "aria-live": "polite", text: "Lade Beschreibung …" }));
    try { daten = zustand.manifeste[name] = await json(`/api/plugins/${encodeURIComponent(name)}/manifest`); }
    catch (e) { fuelle(main, el("h2", { text: name }), el("p", { class: "fehler", text: e.message }), el("a", { href: "#/", text: "Zur Übersicht" })); return; }
  }
  const { plugin: p, manifest: m } = daten;
  const eps = m.service?.endpoints || [];
  const aktiv = eps.find((e) => e.id === endpunktId);
  const filter = el("input", { type: "search", id: "filter", placeholder: "z. B. kontakte, POST", "aria-describedby": "filter-hilfe" });
  const listeBox = el("div");
  const zeichneListe = () => fuelle(listeBox, liste(name, eps, filter.value.trim().toLowerCase(), endpunktId));
  filter.addEventListener("input", zeichneListe); zeichneListe();
  const info = zustand.plugins.find((x) => x.name === name);
  fuelle(main, 
    el("h2", {}, p.titel, " ", el("span", { class: "pill", text: m.version }), " ",
      el("span", { class: "pill blau", text: m["x-eduksx"]?.quelle_beschreibung === "plugin.json" ? "Beschreibung: plugin.json" : "Beschreibung aus openapi.json" })),
    m.description ? el("p", { text: m.description }) : null,
    m.data_notice ? el("p", { class: "warn", text: "Datenschutz: " + m.data_notice }) : null,
    el("p", { class: "leise" }, `${eps.length} Endpunkte · Adresse `, el("span", { class: "pfad", text: p.base_url }), " · ",
      el("a", { href: p.base_url + "/docs", target: "_blank", rel: "noopener", text: "Swagger der API" }),
      name === "escola" ? [" · ", el("a", { href: p.base_url + "/testseite", target: "_blank", rel: "noopener", text: "Escola-Testseite (Workflows)" })] : null,
      " · ", el("a", { href: "#", onclick: (ev) => { ev.preventDefault(); herunterladen(new Blob([JSON.stringify(m, null, 2)], { type: "application/json" }), `${m.id}-plugin.json`); }, text: "plugin.json herunterladen" }),
      " · ", el("a", { href: "#", onclick: async (ev) => { ev.preventDefault(); delete zustand.manifeste[name]; await json(`/api/plugins/${name}/manifest?neu=true`).then((d) => { zustand.manifeste[name] = d; route(); }).catch((e) => alarm(e.message)); }, text: "neu laden" })),
    info && !info.api_key_gesetzt ? el("p", { class: "warn", text: `Kein API-Key hinterlegt (${name.toUpperCase()}_API_KEY in der Umgebung oder apis/${name}/.env). Hat die API einen Key gesetzt, antwortet sie mit 401.` }) : null,
    p.sitzung ? sitzungsBox(name, p.sitzung) : null,
    el("div", { class: "zwei" },
      el("nav", { class: "karte liste", "aria-label": `Endpunkte ${p.titel}` },
        el("label", { for: "filter", text: "Endpunkte filtern" }), el("span", { id: "filter-hilfe", class: "sr", text: "Filtert nach Pfad, Methode und Beschriftung" }), filter, listeBox),
      el("section", { class: "karte", "aria-label": "Tester" }, aktiv ? tester(name, p, aktiv) : el("p", { class: "leise", text: "Links einen Endpunkt wählen." }))));
  if (aktiv) document.querySelector("[data-tester-titel]")?.focus();
}

function liste(name, eps, f, aktivId) {
  const gruppen = new Map();
  for (const e of eps) {
    if (f && !`${e.method} ${e.path} ${e.label} ${e.group || ""}`.toLowerCase().includes(f)) continue;
    const g = e.group || "Allgemein"; if (!gruppen.has(g)) gruppen.set(g, []); gruppen.get(g).push(e);
  }
  if (!gruppen.size) return el("p", { class: "leise", text: "Kein Endpunkt passt." });
  return el("div", {}, [...gruppen].map(([g, liste]) => el("details", { open: true },
    el("summary", {}, g, " ", el("span", { class: "leise", text: `(${liste.length})` })),
    el("ul", {}, liste.map((e) => el("li", {}, el("a", { href: `#/plugin/${name}/${e.id}`, "aria-current": e.id === aktivId ? "page" : null },
      el("span", { class: `m ${e.method}`, text: e.method }),
      el("span", {}, el("span", { class: "pfad", text: e.path }), el("br"), el("span", { class: "leise", text: e.label })),
      e.danger ? el("span", { class: "pill gelb", title: "schreibend", text: "✏️", "aria-label": "schreibend" }) : null)))))));
}

// ----------------------------------------------------------------------------------------- Sitzung (Escola: 2FA)
function sitzungsKey(name) { return `sitzung:${name}`; }
function sitzungsBox(name, s) {
  const aktiv = store.get(sitzungsKey(name));
  const meldung = el("p", { "aria-live": "polite" });
  const box = el("section", { class: "karte", "aria-label": "Anmeldung" }, el("h3", { text: "Anmeldung" }),
    s.hinweis ? el("p", { class: "leise", text: s.hinweis }) : null, meldung);
  const zeigen = (text, cls = "") => { meldung.className = cls; meldung.textContent = text; };
  const rufe = async (m, pfad, body) => {
    const h = { "Content-Type": "application/json" }; const tok = store.get(sitzungsKey(name)); if (tok) h[s.header] = tok;
    const r = await plattform(`/api/plugins/${name}/aufruf${pfad}`, { method: m, headers: h, body: body ? JSON.stringify(body) : undefined });
    const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.meldung || j.detail || `HTTP ${r.status}`); return j;
  };
  if (aktiv) {
    zeigen("Sitzung vorhanden – Status wird geprüft …");
    rufe("GET", s.status || "/auth/status").then((j) => zeigen(`Sitzung: ${j.status || "aktiv"}`, j.status === "angemeldet" ? "pill ok" : "pill gelb"))
      .catch((e) => zeigen(`Sitzung ungültig: ${e.message}`, "fehler"));
    box.append(el("div", { class: "knoepfe" }, el("button", { class: "sekundaer", onclick: async () => {
      try { await rufe("POST", "/auth/logout"); } catch { /* egal */ } store.set(sitzungsKey(name), null); route(); }, text: "Abmelden" })));
    return box;
  }
  const benutzer = el("input", { type: "text", id: "s-benutzer", autocomplete: "username" });
  const passwort = el("input", { type: "password", id: "s-passwort", autocomplete: "current-password" });
  const code = el("input", { type: "text", id: "s-code", inputmode: "numeric", autocomplete: "one-time-code" });
  const codeTeil = el("div", { hidden: true }, el("label", { for: "s-code", text: "2FA-Code" }), code,
    el("div", { class: "knoepfe" }, el("button", { type: "button", onclick: async () => {
      try { const j = await rufe("POST", "/auth/2fa", { code: code.value.trim() }); if (j.session) store.set(sitzungsKey(name), j.session); zeigen("Angemeldet.", "pill ok"); route(); }
      catch (e) { zeigen(e.message, "fehler"); } }, text: "Code bestätigen" }),
      el("button", { type: "button", class: "sekundaer", onclick: async () => { try { await rufe("POST", "/auth/2fa/erneut"); zeigen("Neuer Code gesendet."); } catch (e) { zeigen(e.message, "fehler"); } }, text: "Code erneut senden" })));
  const form = el("form", { onsubmit: async (ev) => {
    ev.preventDefault(); zeigen("Anmeldung läuft …");
    try {
      const j = await rufe("POST", s.anmeldung || "/auth/login", { benutzername: benutzer.value, passwort: passwort.value });
      passwort.value = "";
      if (j[s.feld || "session"]) store.set(sitzungsKey(name), j[s.feld || "session"]);
      if (j.status === "2fa_erforderlich") { codeTeil.hidden = false; code.focus(); zeigen("Code aus der Authentifizierungs-App bzw. SMS eingeben."); }
      else if (j.status === "angemeldet") { zeigen("Angemeldet.", "pill ok"); route(); }
      else zeigen(`Status: ${j.status}`, "warn");
    } catch (e) { zeigen(e.message, "fehler"); }
  } }, el("div", { class: "raster" }, el("div", {}, el("label", { for: "s-benutzer", text: "Benutzername" }), benutzer),
      el("div", {}, el("label", { for: "s-passwort", text: "Passwort" }), passwort)),
    el("div", { class: "knoepfe" }, el("button", { text: "Anmelden" })));
  box.append(form, codeTeil);
  return box;
}

// ----------------------------------------------------------------------------------------- Tester
function beispielText(e) { return e.body === undefined ? "" : JSON.stringify(e.body, null, 2); }

function tester(name, p, e) {
  const werte = zustand.werte[name] || {};
  const params = e.params || [];
  const pfadP = params.filter((x) => x.in === "path");
  const queryP = params.filter((x) => (x.in || "query") === "query");
  const kopfP = params.filter((x) => x.in === "header");
  const feldId = (x) => `p-${x.in || "query"}-${x.name}`;
  const eingabe = (x, beispiel) => {
    const id = feldId(x);
    const vorgabe = x.in === "path" ? (werte[x.name] ?? werte[x.name.replace(/_id$/, "")] ?? (x.name === "id" ? werte.id : "") ?? "") : (beispiel ? (x.example ?? x.default ?? "") : (x.default ?? ""));
    const feld = x.choices ? el("select", { id }, x.required ? null : el("option", { value: "", text: "–" }), x.choices.map((c) => el("option", { value: c, text: c, selected: String(vorgabe) === c })))
      : el("input", { type: "text", id, value: vorgabe ?? "", required: x.required || null, "aria-describedby": x.help ? id + "-h" : null });
    return el("div", {}, el("label", { for: id }, x.name, x.required ? " *" : "", x.default != null ? el("span", { class: "leise", text: ` (Vorgabe ${x.default})` }) : null),
      feld, x.help ? el("span", { id: id + "-h", class: "leise", text: x.help }) : null);
  };
  const box = el("div");
  const zeichneFelder = (mitBeispiel) => {
    fuelle(box, 
      pfadP.length ? [el("h3", { text: "Pfad" }), el("div", { class: "raster" }, pfadP.map((x) => eingabe(x, mitBeispiel)))] : null,
      queryP.length ? [el("h3", { text: "Abfrage" }), el("div", { class: "raster" }, queryP.map((x) => eingabe(x, mitBeispiel)))] : null,
      kopfP.length ? [el("h3", { text: "Kopfzeilen" }), el("div", { class: "raster" }, kopfP.map((x) => eingabe(x, mitBeispiel)))] : null);
  };
  zeichneFelder(true);

  let body = null, bodyFehler = null, formBox = null;
  if (e.body !== undefined || (e.fields && !e.form)) {
    bodyFehler = el("p", { id: "body-fehler", class: "leise", "aria-live": "polite" });
    body = el("textarea", { id: "body", "aria-describedby": "body-fehler", spellcheck: "false" });
    body.value = beispielText(e);
    const pruefen = () => { if (!body.value.trim()) { body.removeAttribute("aria-invalid"); bodyFehler.textContent = ""; return true; }
      try { JSON.parse(body.value); body.removeAttribute("aria-invalid"); bodyFehler.textContent = "JSON gültig"; return true; }
      catch (ex) { body.setAttribute("aria-invalid", "true"); bodyFehler.textContent = "JSON ungültig: " + ex.message; return false; } };
    body.addEventListener("input", pruefen); pruefen(); body._pruefen = pruefen;
  }
  if (e.form) {
    formBox = el("div", { class: "raster" }, e.form.map((f) => {
      const id = `f-${f.name}`;
      const feld = f.type === "file" ? el("input", { type: "file", id, multiple: f.multiple || null, required: f.required || null })
        : f.type === "boolean" ? el("select", { id }, el("option", { value: "", text: "–" }), el("option", { value: "true", text: "true" }), el("option", { value: "false", text: "false" }))
        : el("input", { type: "text", id, value: f.example != null && typeof f.example !== "object" ? String(f.example) : "" });
      return el("div", {}, el("label", { for: id }, f.name, f.required ? " *" : ""), feld, f.help ? el("span", { class: "leise", text: f.help }) : null);
    }));
  }
  const probelauf = e.probelauf ? el("input", { type: "checkbox", id: "probelauf", checked: true }) : null;
  const ergebnis = el("div", { "aria-live": "polite" });
  const senden = el("button", { type: "submit", text: e.danger ? "Senden (schreibend)" : "Senden" });

  const form = el("form", { onsubmit: async (ev) => {
    ev.preventDefault();
    if (body && body._pruefen && !body._pruefen()) { body.focus(); return; }
    let pfad = e.path;
    for (const x of pfadP) {
      const v = $(feldId(x)).value.trim();
      if (!v) { $(feldId(x)).focus(); fuelle(ergebnis, el("p", { class: "fehler", text: `Pfadparameter «${x.name}» fehlt.` })); return; }
      pfad = pfad.replace(`{${x.name}}`, encodeURIComponent(v));
    }
    const q = new URLSearchParams();
    for (const x of queryP) { const v = $(feldId(x)).value.trim(); if (v !== "") q.append(x.name, v); }
    const istProbe = !!(probelauf && probelauf.checked);
    if (istProbe) q.set("probelauf", "true");
    const h = {};
    for (const x of kopfP) { const v = $(feldId(x)).value.trim(); if (v) h[x.name] = v; }
    const tok = p.sitzung && store.get(sitzungsKey(name)); if (tok) h[p.sitzung.header] = tok;
    if (e.danger && !istProbe) {
      if (!(await bestaetigen(`${e.method} ${pfad} – ${e.label}`))) { fuelle(ergebnis, el("p", { class: "leise", text: "Abgebrochen." })); return; }
      h["X-Testplattform-Bestaetigt"] = "ja";
    }
    let inhalt;
    if (formBox) {
      inhalt = new FormData();
      for (const f of e.form) {
        const feld = $(`f-${f.name}`);
        if (f.type === "file") for (const d of feld.files) inhalt.append(f.name, d);
        else if (feld.value !== "") inhalt.append(f.name, feld.value);
      }
    } else if (body && body.value.trim()) { inhalt = body.value; h["Content-Type"] = "application/json"; }
    senden.disabled = true; fuelle(ergebnis, el("p", { text: "Aufruf läuft …" }));
    try {
      const url = `/api/plugins/${encodeURIComponent(name)}/aufruf${pfad}${q.toString() ? "?" + q : ""}`;
      const r = await plattform(url, { method: e.method, headers: h, body: inhalt });
      await antwortZeigen(name, r, ergebnis, istProbe);
    } catch (ex) { fuelle(ergebnis, el("p", { class: "fehler", text: ex.message })); }
    finally { senden.disabled = false; }
  } },
    box,
    body ? [el("h3", {}, el("label", { for: "body", text: "Body (JSON)" })), body, bodyFehler] : null,
    formBox ? [el("h3", { text: "Formular (multipart)" }), formBox] : null,
    e.fields && body ? el("details", {}, el("summary", { text: "Mögliche Werte" }), el("table", {}, el("thead", {}, el("tr", {}, ["Feld", "Typ", "Pflicht", "Beispiel", "Hinweis"].map((t) => el("th", { scope: "col", text: t })))),
      el("tbody", {}, e.fields.map((f) => el("tr", {}, el("td", { class: "pfad", text: f.name }), el("td", { text: f.type || "" }), el("td", { text: f.required ? "ja" : "" }),
        el("td", { class: "pfad", text: f.example === undefined ? "" : JSON.stringify(f.example) }), el("td", { text: [f.help, f.choices ? "Werte: " + f.choices.join(", ") : ""].filter(Boolean).join(" · ") })))))) : null,
    probelauf ? el("label", { class: "check", for: "probelauf" }, probelauf, "Probelauf (?probelauf=true) – schreibt nichts") : null,
    e.danger && !e.probelauf ? el("p", { class: "warn", text: "Schreibender Aufruf ohne Probelauf: vor dem Senden wird nachgefragt." }) : null,
    el("div", { class: "knoepfe" }, senden,
      el("button", { type: "button", class: "sekundaer", onclick: () => { zeichneFelder(true); if (body) { body.value = beispielText(e); body._pruefen(); } }, text: "Beispiel einsetzen" }),
      el("button", { type: "button", class: "sekundaer", onclick: () => { zeichneFelder(false); if (body) { body.value = ""; body._pruefen(); } }, text: "Felder löschen" }),
      body ? el("button", { type: "button", class: "sekundaer", onclick: () => { try { body.value = JSON.stringify(JSON.parse(body.value), null, 2); } catch { /* bleibt */ } body._pruefen(); }, text: "Formatieren" }) : null));

  return el("div", {},
    el("h2", { tabindex: "-1", "data-tester-titel": true }, el("span", { class: `m ${e.method}`, text: e.method }), " ", el("span", { class: "pfad", text: e.path })),
    el("p", {}, e.label, " ", el("span", { class: `pill ${e.status === "full" ? "ok" : e.status === "planned" ? "err" : "gelb"}`, text: { full: "bestätigt", partial: "teilweise / nicht live geprüft", planned: "geplant" }[e.status] || e.status }),
      e.danger ? [" ", el("span", { class: "pill gelb", text: "schreibend" })] : null),
    e.note ? el("p", { class: "leise", style: "white-space:pre-line", text: e.note }) : null,
    e.status === "planned" ? el("p", { class: "warn", text: "Nur geplant – nicht aufrufbar." }) : form,
    ergebnis);
}

function herunterladen(blob, name) {
  const a = el("a", { href: URL.createObjectURL(blob), download: name }); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
function alarm(text) { $("inhalt").prepend(el("p", { class: "fehler", role: "alert", text })); }

function idsMerken(name, daten) {
  const ziel = (zustand.werte[name] ||= {});
  const obj = Array.isArray(daten) ? daten[0] : (daten && typeof daten === "object" ? (Object.values(daten).find(Array.isArray)?.[0] ?? daten) : null);
  if (!obj || typeof obj !== "object") return;
  for (const [k, v] of Object.entries(obj)) if ((typeof v === "string" || typeof v === "number") && /(^id$|_id$|^guid$|guid$|^pid$|^fremdkey$)/i.test(k)) ziel[k] = String(v);
  if (obj.guid) ziel.guid = String(obj.guid);
  if (obj.id != null) { ziel.id = String(obj.id); ziel.pid ??= String(obj.id); }
}

async function antwortZeigen(name, r, box, probe) {
  const typ = r.headers.get("content-type") || "";
  const dauer = r.headers.get("x-dauer-ms");
  const kopf = el("p", {}, el("span", { class: `pill ${r.ok ? "ok" : r.status === 428 ? "gelb" : "err"}`, text: `HTTP ${r.status}` }),
    dauer ? ` · ${dauer} ms` : "", probe ? " · Probelauf" : "", typ ? [" · ", el("span", { class: "pfad", text: typ.split(";")[0] })] : null);
  if (typ.includes("json")) {
    const text = await r.text(); let daten = null;
    try { daten = JSON.parse(text); } catch { /* als Text */ }
    if (r.ok && daten) idsMerken(name, daten);
    fuelle(box, kopf, el("pre", { class: "antwort", tabindex: "0", "aria-label": "Antwort", text: daten ? JSON.stringify(daten, null, 2) : text }),
      el("div", { class: "knoepfe" }, el("button", { type: "button", class: "sekundaer", onclick: () => navigator.clipboard?.writeText(daten ? JSON.stringify(daten, null, 2) : text), text: "Kopieren" })));
    return;
  }
  const blob = await r.blob();
  const dateiname = (r.headers.get("content-disposition") || "").match(/filename="?([^";]+)/)?.[1] || `antwort.${typ.includes("csv") ? "csv" : typ.includes("pdf") ? "pdf" : "txt"}`;
  const vorschau = typ.startsWith("text/") ? (await blob.text()).slice(0, 3000) : null;
  fuelle(box, kopf, el("div", { class: "knoepfe" }, el("button", { type: "button", onclick: () => herunterladen(blob, dateiname), text: `${dateiname} herunterladen (${Math.ceil(blob.size / 1024)} KB)` })),
    vorschau != null ? el("pre", { class: "antwort", tabindex: "0", "aria-label": "Vorschau", text: vorschau }) : null);
}

async function protokollSeite() {
  const main = $("inhalt");
  let liste = [];
  try { liste = await json("/api/protokoll"); } catch (e) { fuelle(main, el("p", { class: "fehler", text: e.message })); return; }
  fuelle(main, el("h2", { text: "Protokoll" }),
    el("p", { class: "leise", text: "Letzte 300 Aufrufe seit dem Start der Testplattform, nur im Arbeitsspeicher. Ohne Parameterwerte, Bodys und Zugangsdaten." }),
    liste.length ? el("table", {}, el("thead", {}, el("tr", {}, ["Zeit", "Plugin", "Methode", "Endpunkt", "Status", "Probelauf", "Dauer"].map((t) => el("th", { scope: "col", text: t })))),
      el("tbody", {}, liste.map((x) => el("tr", {}, el("td", { text: x.zeit.replace("T", " ") }), el("td", { text: x.plugin }), el("td", {}, el("span", { class: `m ${x.methode}`, text: x.methode })),
        el("td", { class: "pfad", text: x.pfad }), el("td", { text: x.status ?? "nicht erreichbar" }), el("td", { text: x.probelauf ? "ja" : x.schreibend ? "nein – geschrieben" : "" }), el("td", { text: `${x.dauer_ms} ms` })))))
      : el("p", { text: "Noch keine Aufrufe." }));
}

// ----------------------------------------------------------------------------------------- Routing
function route() {
  const teile = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (teile[0] === "plugin" && teile[1]) pluginSeite(teile[1], teile[2]);
  else if (teile[0] === "protokoll") protokollSeite();
  else start();
}
window.addEventListener("hashchange", route);
json("/api/info").then((i) => { $("version").textContent = "Version " + i.version; }).catch(() => {}).finally(route);
