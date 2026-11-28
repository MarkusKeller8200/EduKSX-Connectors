/* Testplattform EduKSX-Connectors (#41, #43, #51). Zwei Betriebsarten:
   - Plattform (lokal, testplattform/app.py): Aufrufe über /api/…, API-Keys bleiben auf dem Server.
   - Direkt (GitHub Pages, plugins.json vorhanden): der Browser ruft die lokal laufenden APIs selbst auf; Adresse und
     API-Key je API gibt man auf der Startseite ein (Key nur im Browser-Tab).
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

// ----------------------------------------------------------------------------------------- Betriebsarten
const lokal = {  // Adresse dauerhaft (localStorage), API-Key nur im Tab (sessionStorage)
  adresse: (p) => { try { return localStorage.getItem(`adresse:${p.name}`) || `http://127.0.0.1:${p.port}`; } catch { return `http://127.0.0.1:${p.port}`; } },
  setzeAdresse: (name, v) => { try { v ? localStorage.setItem(`adresse:${name}`, v.replace(/\/+$/, "")) : localStorage.removeItem(`adresse:${name}`); } catch { /* egal */ } },
  key: (name) => store.get(`key:${name}`) || "",
};
const direktProtokoll = [];
let backend = null;

const plattformBackend = {
  direkt: false,
  info: () => json("api/info"),
  plugins: () => json("api/plugins"),
  manifest: (name, neu) => json(`api/plugins/${encodeURIComponent(name)}/manifest${neu ? "?neu=true" : ""}`),
  aufruf: (name, pfad, opt) => plattform(`api/plugins/${encodeURIComponent(name)}/aufruf${pfad}`, opt),
  protokoll: () => json("api/protokoll"),
};

function direktBackend(liste) {
  const nachName = Object.fromEntries(liste.map((p) => [p.name, p]));
  const kopf = (name, extra = {}) => { const h = new Headers(extra); const k = lokal.key(name); if (k) h.set("X-API-Key", k); return h; };
  const oeffentlich = (p) => ({ ...p, base_url: lokal.adresse(p), api_key_gesetzt: !!lokal.key(p.name) });
  return {
    direkt: true,
    info: async () => ({ version: liste.version || "", token_noetig: false }),
    plugins: async () => Promise.all(liste.map(async (p) => {
      const e = oeffentlich(p);
      try {
        const r = await fetch(e.base_url + "/status", { headers: kopf(p.name) });
        e.erreichbar = true; e.status_code = r.status; e.status = await r.json().catch(() => null);
      } catch { e.erreichbar = false; e.status_code = null; e.status = null; }
      return e;
    })),
    manifest: async (name) => {
      const p = nachName[name]; if (!p) throw new Error(`Plugin «${name}» unbekannt`);
      const e = oeffentlich(p);
      let r, fehler;
      try { r = await fetch(e.base_url + "/plugin.json", { headers: kopf(name) }); }
      catch { fehler = `${p.titel} nicht erreichbar unter ${e.base_url} – API lokal starten (start-testplattform) und Adresse prüfen.`; }
      if (!fehler && r.status === 401) fehler = `${p.titel}: API-Key fehlt oder ist falsch – auf der Startseite eintragen.`;
      else if (!fehler && !r.ok) fehler = `${p.titel}: /plugin.json antwortet mit ${r.status} (API ohne shared/? Lokal aus dem Repo starten).`;
      if (!fehler) { const m = await r.json(); (m["x-eduksx"] ||= {}).quelle_beschreibung = "plugin.json"; return { plugin: e, manifest: m }; }
      const s = await statischesManifest(name);  // Beschreibung vom Bau der Seite: Doku lesbar, Tester ohne API nicht
      if (s) return { plugin: e, manifest: s, hinweis: fehler };
      throw new Error(fehler);
    },
    statisch: (name) => statischesManifest(name),
    aufruf: async (name, pfad, opt) => {
      const p = nachName[name]; const t0 = performance.now();
      const h = kopf(name, opt.headers || {}); h.delete("X-Testplattform-Bestaetigt");
      const eintrag = { zeit: new Date().toISOString().slice(0, 19), plugin: name, methode: opt.method, pfad: pfad.split("?")[0],
        probelauf: /[?&]probelauf=true/.test(pfad), schreibend: !!opt.schreibend };
      try {
        const r = await fetch(lokal.adresse(p) + pfad, { ...opt, headers: h });
        direktProtokoll.push({ ...eintrag, status: r.status, dauer_ms: Math.round(performance.now() - t0) });
        return r;
      } catch (ex) {
        direktProtokoll.push({ ...eintrag, status: null, dauer_ms: Math.round(performance.now() - t0) });
        throw new Error(`${p.titel} nicht erreichbar (${lokal.adresse(p)}) – läuft die API lokal? Browser-Freigabe für das lokale Netzwerk erteilt?`);
      }
    },
    protokoll: async () => [...direktProtokoll].reverse(),
  };
}

async function statischesManifest(name) {
  try {
    const r = await fetch(`manifeste/${encodeURIComponent(name)}.json`, { cache: "no-store" });
    if (!r.ok) return null;
    const m = await r.json(); (m["x-eduksx"] ||= {}).quelle_beschreibung = "statisch";
    return m;
  } catch { return null; }
}

async function waehleBackend() {
  try {
    const r = await fetch("plugins.json", { cache: "no-store" });
    if (r.ok) { const d = await r.json(); const b = direktBackend(d.plugins || []); b.version = d.version; b.info = async () => ({ version: d.version }); return b; }
  } catch { /* Plattform */ }
  return plattformBackend;
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
  try { zustand.plugins = await backend.plugins(); } catch (e) { fuelle(main, el("p", { class: "fehler", text: e.message })); return; }
  navigation();
  fuelle(main,
    backend.direkt ? direktHinweis() : null,
    el("h2", { text: "Eingebundene APIs" }),
    el("p", { class: "leise", text: "Jede API unter apis/ ist ein Plugin. Die Testseite entsteht aus ihrer Beschreibung (GET /plugin.json bzw. /openapi.json)." }),
    el("div", { class: "karten" }, zustand.plugins.map(karte)));
}
function direktHinweis() {
  return el("section", { class: "warn", "aria-label": "Hinweis" },
    el("strong", { text: "Diese Seite läuft auf GitHub Pages – die APIs müssen lokal laufen." }),
    el("ul", {},
      el("li", { text: "Repository EduKSX-Connectors auschecken und start-testplattform.command (macOS/Linux) bzw. start-testplattform.bat (Windows) doppelklicken – startet alle APIs. Oder eine API einzeln starten." }),
      el("li", { text: "Je API die Adresse prüfen und den API-Key eintragen (steht in apis/<name>/.env als <NAME>_API_KEY). Der Key bleibt nur in diesem Browser-Tab." }),
      el("li", { text: "Die Daten gehen direkt vom Browser an die API auf diesem Rechner, nicht über GitHub. Beim ersten Aufruf fragt der Browser evtl. nach dem Zugriff aufs lokale Netzwerk – erlauben." }),
      el("li", { text: "Chrome, Edge oder Firefox verwenden; Safari blockiert Aufrufe an http://127.0.0.1 von https-Seiten." })));
}
function direktEinstellungen(p) {
  const idA = `adr-${p.name}`, idK = `key-${p.name}`;
  const adresse = el("input", { type: "text", id: idA, value: p.base_url, spellcheck: "false" });
  const key = el("input", { type: "password", id: idK, autocomplete: "off", placeholder: p.api_key_gesetzt ? "hinterlegt (leer lassen = behalten)" : "" });
  return el("form", { onsubmit: (ev) => {
    ev.preventDefault();
    lokal.setzeAdresse(p.name, adresse.value.trim() === `http://127.0.0.1:${p.port}` ? "" : adresse.value.trim());
    if (key.value) store.set(`key:${p.name}`, key.value);
    zustand.manifeste = {}; start();
  } }, el("label", { for: idA, text: "Adresse" }), adresse, el("label", { for: idK, text: "API-Key" }), key,
    el("div", { class: "knoepfe" }, el("button", { text: "Übernehmen" }),
      p.api_key_gesetzt ? el("button", { type: "button", class: "sekundaer", onclick: () => { store.set(`key:${p.name}`, null); zustand.manifeste = {}; start(); }, text: "Key entfernen" }) : null));
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
      el("dt", { text: "API-Key" }), el("dd", { text: p.api_key_gesetzt ? (backend.direkt ? "eingetragen (nur in diesem Tab)" : "hinterlegt (auf dem Server)") : "keiner hinterlegt" }),
      p.status?.version ? [el("dt", { text: "Version laut API" }), el("dd", { text: p.status.version })] : null),
    backend.direkt ? el("details", { open: !p.api_key_gesetzt || !p.erreichbar }, el("summary", { text: "Adresse und API-Key" }), direktEinstellungen(p)) : null,
    el("p", {}, el("a", { href: `#/plugin/${p.name}`, text: `Testseite ${p.titel} öffnen` }), " · ",
      el("a", { href: `#/doku/${p.name}`, text: "Dokumentation" })));
}
function navigation() {
  fuelle($("hauptnav"), ...zustand.plugins.map((p) => el("a", { href: `#/plugin/${p.name}`, text: p.titel })),
    el("a", { href: "#/doku", text: "Dokumentation" }));
}

async function pluginSeite(name, endpunktId) {
  const main = $("inhalt");
  if (!zustand.plugins.length) { try { zustand.plugins = await backend.plugins(); navigation(); } catch { /* weiter */ } }
  let daten = zustand.manifeste[name];
  if (!daten) {
    fuelle(main, el("p", { "aria-live": "polite", text: "Lade Beschreibung …" }));
    try { daten = zustand.manifeste[name] = await backend.manifest(name); }
    catch (e) { fuelle(main, el("h2", { text: name }), el("p", { class: "fehler", text: e.message }), el("a", { href: "#/", text: "Zur Übersicht" })); return; }
  }
  const { plugin: p, manifest: m } = daten;
  const eps = m.service?.endpoints || [];
  const aktiv = eps.find((e) => e.id === endpunktId);
  const filter = el("input", { type: "search", id: "filter", placeholder: "z. B. kontakte, POST", "aria-describedby": "filter-hilfe" });
  const listeBox = el("div");
  const zeichneListe = () => fuelle(listeBox, liste(name, eps, filter.value.trim().toLowerCase(), endpunktId, m));
  filter.addEventListener("input", zeichneListe); zeichneListe();
  const info = zustand.plugins.find((x) => x.name === name);
  fuelle(main, 
    el("h2", {}, p.titel, " ", el("span", { class: "pill", text: m.version }), " ",
      el("span", { class: "pill blau", text: m["x-eduksx"]?.quelle_beschreibung === "plugin.json" ? "Beschreibung: plugin.json" : "Beschreibung aus openapi.json" })),
    m.description ? el("p", { text: m.description }) : null,
    m.data_notice ? el("p", { class: "warn", text: "Datenschutz: " + m.data_notice }) : null,
    daten.hinweis ? el("p", { class: "warn", text: daten.hinweis + " Angezeigt wird die Beschreibung vom Bau dieser Seite; Testen geht erst mit laufender API." }) : null,
    el("p", { class: "leise" }, `${eps.length} Endpunkte · `, el("a", { href: `#/doku/${name}`, text: "Dokumentation" }), " · Adresse ", el("span", { class: "pfad", text: p.base_url }), " · ",
      el("a", { href: p.base_url + "/docs", target: "_blank", rel: "noopener", text: "Swagger der API" }),
      name === "escola" ? [" · ", el("a", { href: p.base_url + "/testseite", target: "_blank", rel: "noopener", text: "Escola-Testseite (Workflows)" })] : null,
      " · ", el("a", { href: "#", onclick: (ev) => { ev.preventDefault(); herunterladen(new Blob([JSON.stringify(m, null, 2)], { type: "application/json" }), `${m.id}-plugin.json`); }, text: "plugin.json herunterladen" }),
      " · ", el("a", { href: "#", onclick: async (ev) => { ev.preventDefault(); delete zustand.manifeste[name]; await backend.manifest(name, true).then((d) => { zustand.manifeste[name] = d; route(); }).catch((e) => alarm(e.message)); }, text: "neu laden" })),
    info && !info.api_key_gesetzt ? el("p", { class: "warn", text: backend.direkt
      ? `Kein API-Key eingetragen – auf der Startseite unter «Adresse und API-Key» eintragen (${name.toUpperCase()}_API_KEY aus apis/${name}/.env).`
      : `Kein API-Key hinterlegt (${name.toUpperCase()}_API_KEY in der Umgebung oder apis/${name}/.env). Hat die API einen Key gesetzt, antwortet sie mit 401.` }) : null,
    p.sitzung ? sitzungsBox(name, p.sitzung) : null,
    el("div", { class: "zwei" },
      el("nav", { class: "karte liste", "aria-label": `Endpunkte ${p.titel}` },
        el("label", { for: "filter", text: "Endpunkte filtern" }), el("span", { id: "filter-hilfe", class: "sr", text: "Filtert nach Pfad, Methode und Beschriftung" }), filter, listeBox),
      el("section", { class: "karte", "aria-label": "Tester" }, aktiv ? tester(name, p, aktiv) : el("p", { class: "leise", text: "Links einen Endpunkt wählen." }))));
  if (aktiv) document.querySelector("[data-tester-titel]")?.focus();
}

function gruppieren(eps, m, f = "") {
  const gruppen = new Map((m?.["x-eduksx"]?.gruppen || []).map((g) => [g.name, []]));
  for (const e of eps) {
    if (f && !`${e.method} ${e.path} ${e.label} ${e.group || ""}`.toLowerCase().includes(f)) continue;
    const g = e.group || "Allgemein"; if (!gruppen.has(g)) gruppen.set(g, []); gruppen.get(g).push(e);
  }
  return [...gruppen].filter(([, l]) => l.length);
}

function liste(name, eps, f, aktivId, m) {
  const gruppen = new Map(gruppieren(eps, m, f));
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
    const r = await backend.aufruf(name, pfad, { method: m, headers: h, body: body ? JSON.stringify(body) : undefined });
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
      const t0 = performance.now();
      const r = await backend.aufruf(name, `${pfad}${q.toString() ? "?" + q : ""}`, { method: e.method, headers: h, body: inhalt, schreibend: !!e.danger });
      await antwortZeigen(name, r, ergebnis, istProbe, r.headers.get("x-dauer-ms") || String(Math.round(performance.now() - t0)));
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

async function antwortZeigen(name, r, box, probe, dauer) {
  const typ = r.headers.get("content-type") || "";
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

// ----------------------------------------------------------------------------------------- Dokumentation
async function dokuManifest(name) {
  if (backend.statisch) { const s = await backend.statisch(name); if (s) return s; }  // GitHub Pages: ohne laufende API
  return (zustand.manifeste[name] ||= await backend.manifest(name)).manifest;
}
async function dokuSeite(name) {
  const main = $("inhalt");
  if (!zustand.plugins.length) { try { zustand.plugins = await backend.plugins(); navigation(); } catch { /* weiter */ } }
  if (!name) {
    fuelle(main, el("h2", { text: "Dokumentation der APIs" }),
      el("p", { class: "leise", text: "Beschreibung aller Endpunkte, nach Themen gruppiert. Lesbar ohne laufende API." }),
      el("ul", {}, zustand.plugins.map((p) => el("li", {}, el("a", { href: `#/doku/${p.name}`, text: p.titel }), " ",
        el("span", { class: "pill", text: p.version }), p.beschreibung ? [" – ", p.beschreibung] : null))));
    return;
  }
  fuelle(main, el("p", { "aria-live": "polite", text: "Lade Dokumentation …" }));
  let m;
  try { m = await dokuManifest(name); } catch (e) { fuelle(main, el("p", { class: "fehler", text: e.message })); return; }
  const eps = m.service?.endpoints || [];
  const gruppen = gruppieren(eps, m);
  const info = Object.fromEntries((m["x-eduksx"]?.gruppen || []).map((g) => [g.name, g.beschreibung]));
  const anker = (g) => "g-" + g.toLowerCase().replace(/[^a-z0-9äöü]+/g, "-");
  const sprung = (id) => (ev) => { ev.preventDefault(); document.getElementById(id)?.scrollIntoView(); document.getElementById(id)?.focus(); };
  fuelle(main,
    el("h2", {}, m.name, " ", el("span", { class: "pill", text: m.version })),
    m.description ? el("p", { text: m.description }) : null,
    m.data_notice ? el("p", { class: "warn", text: "Datenschutz: " + m.data_notice }) : null,
    el("p", { class: "leise" }, `${eps.length} Endpunkte in ${gruppen.length} Themen · `,
      el("a", { href: `#/plugin/${name}`, text: "Testseite" }), " · Anmeldung: Kopfzeile ", el("code", { text: "X-API-Key" }),
      m["x-eduksx"]?.sitzung ? [", Escola-Sitzung: ", el("code", { text: m["x-eduksx"].sitzung.header })] : null,
      " · ✏️ = schreibt (zuerst mit probelauf=true testen)"),
    el("nav", { class: "karte", "aria-label": "Themen" }, el("strong", { text: "Themen" }),
      el("ul", { class: "spalten" }, gruppen.map(([g, l]) => el("li", {}, el("a", { href: "#", onclick: sprung(anker(g)), text: g }),
        " ", el("span", { class: "leise", text: `(${l.length})` }))))),
    gruppen.map(([g, l]) => el("section", { class: "karte doku", id: anker(g), tabindex: "-1", "aria-labelledby": anker(g) + "-h" },
      el("h3", { id: anker(g) + "-h", text: g }),
      info[g] ? el("p", { class: "leise", text: info[g] }) : null,
      l.map((e) => dokuEndpunkt(name, e)))));
}
function notiz(e) {  // Beschreibung ohne die Zeile, die schon als Überschrift steht
  const z = String(e.note || "").split("\n");
  if (z.length && z[0].trim().replace(/\.$/, "") === String(e.label || "").trim().replace(/\.$/, "")) z.shift();
  return z.join("\n").trim();
}
function dokuEndpunkt(name, e) {
  const param = (p) => el("tr", {}, el("td", {}, el("code", { text: p.name }), p.required ? el("span", { class: "leise", text: " *" }) : null),
    el("td", { text: p.in === "path" ? "Pfad" : p.in === "header" ? "Kopfzeile" : "Abfrage" }),
    el("td", {}, p.help || "", p.choices ? [" ", el("span", { class: "leise", text: "(" + p.choices.join(", ") + ")" })] : null,
      p.default != null ? [" ", el("span", { class: "leise", text: "Standard: " + p.default })] : null));
  const feld = (f) => el("tr", {}, el("td", {}, el("code", { text: f.name }), f.required ? el("span", { class: "leise", text: " *" }) : null),
    el("td", { text: f.type || "" }), el("td", { text: f.help || "" }));
  const params = e.params || [];
  const felder = e.fields || e.form || [];
  return el("article", { class: "ep" },
    el("h4", {}, el("span", { class: `m ${e.method}`, text: e.method }), " ", el("span", { class: "pfad", text: e.path }), " ",
      e.danger ? el("span", { class: "pill gelb", text: "✏️ schreibt" }) : null, " ",
      e.probelauf ? el("span", { class: "pill blau", text: "Probelauf" }) : null),
    el("p", {}, el("strong", { text: e.label }), " ", el("a", { href: `#/plugin/${name}/${e.id}`, class: "leise", text: "testen" })),
    notiz(e) ? el("p", { class: "notiz", text: notiz(e) }) : null,
    params.length ? el("table", { class: "klein" }, el("thead", {}, el("tr", {}, ["Parameter", "Ort", "Beschreibung"].map((t) => el("th", { scope: "col", text: t })))),
      el("tbody", {}, params.map(param))) : null,
    felder.length ? el("table", { class: "klein" }, el("thead", {}, el("tr", {}, ["Feld im Body", "Typ", "Beschreibung"].map((t) => el("th", { scope: "col", text: t })))),
      el("tbody", {}, felder.map(feld))) : null);
}

async function protokollSeite() {
  const main = $("inhalt");
  let liste = [];
  try { liste = await backend.protokoll(); } catch (e) { fuelle(main, el("p", { class: "fehler", text: e.message })); return; }
  fuelle(main, el("h2", { text: "Protokoll" }),
    el("p", { class: "leise", text: backend.direkt ? "Aufrufe aus diesem Browser-Tab seit dem Öffnen der Seite (nur im Arbeitsspeicher). Ohne Parameterwerte, Bodys und Zugangsdaten." : "Letzte 300 Aufrufe seit dem Start der Testplattform, nur im Arbeitsspeicher. Ohne Parameterwerte, Bodys und Zugangsdaten." }),
    liste.length ? el("table", {}, el("thead", {}, el("tr", {}, ["Zeit", "Plugin", "Methode", "Endpunkt", "Status", "Probelauf", "Dauer"].map((t) => el("th", { scope: "col", text: t })))),
      el("tbody", {}, liste.map((x) => el("tr", {}, el("td", { text: x.zeit.replace("T", " ") }), el("td", { text: x.plugin }), el("td", {}, el("span", { class: `m ${x.methode}`, text: x.methode })),
        el("td", { class: "pfad", text: x.pfad }), el("td", { text: x.status ?? "nicht erreichbar" }), el("td", { text: x.probelauf ? "ja" : x.schreibend ? "nein – geschrieben" : "" }), el("td", { text: `${x.dauer_ms} ms` })))))
      : el("p", { text: "Noch keine Aufrufe." }));
}

// ----------------------------------------------------------------------------------------- Routing
function route() {
  const teile = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (teile[0] === "plugin" && teile[1]) pluginSeite(teile[1], teile[2]);
  else if (teile[0] === "doku") dokuSeite(teile[1]);
  else if (teile[0] === "protokoll") protokollSeite();
  else start();
}
window.addEventListener("hashchange", route);
waehleBackend().then((b) => {
  backend = b;
  document.body.classList.toggle("direkt", b.direkt);
  return b.info().then((i) => { $("version").textContent = "Version " + i.version; });
}).catch(() => {}).finally(route);
