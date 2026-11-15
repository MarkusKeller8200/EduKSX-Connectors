/**
 * Escola Stammdaten-Export (sekbuelach.ch) – nur lesend
 * -----------------------------------------------------
 * Liefert Listen aller Klassen, Fächer, Räume und Lehrpersonen inkl. Escola-IDs.
 *
 * Verwendung: Im eingeloggten Escola-Admin-Bereich (https://www.sekbuelach.ch/admin.php?...)
 * die Browser-Konsole öffnen (F12 → Konsole), dieses Skript einfügen und ausführen:
 *
 *     const daten = await escolaStammdaten();
 *     escolaDownload(daten);          // lädt 4 CSV-Dateien + 1 JSON herunter
 *
 * Authentifizierung: über das bestehende Session-Cookie des Browsers (kein Token nötig).
 * Alle Aufrufe sind lesend. Für Fächer/Räume wird kurz die Bearbeitungsansicht einer
 * Lektion von H_A1a geöffnet und sofort wieder geschlossen (ändert keine Daten).
 */

async function escolaStammdaten(opts = {}) {
  const refClassId = opts.refClassId ?? 92;     // Klasse mit bestehender Lektion (für Fach-/Raumliste)
  const refDay = opts.refDay ?? 'A';            // Montag
  const refLesson = opts.refLesson ?? 2;        // 07.30
  const schoolUnits = opts.schoolUnits ?? [1, 2, 3, 4, 5]; // 1 = Hinterbirch, 2 = Mettmenriet

  const get = async u => (await fetch(u, { credentials: 'same-origin' })).text();
  const post = async (u, p) => (await fetch(u, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
    body: new URLSearchParams(p).toString(),
    credentials: 'same-origin'
  })).text();
  const dom = h => new DOMParser().parseFromString(h, 'text/html');
  const TT = 'inc/ajax/timetable/ajax_functions_timetable.php';

  // 1) Klassen + Arbeitsgruppen: Auswahlliste auf der Stundenplan-Seite
  const page = dom(await get('admin.php?page_request=6&klassen_id=' + refClassId));
  const klassen = [...page.querySelectorAll('#unifiedClassOrWorkgroupChooser option')].map(o => {
    const v = o.value || '';
    const m = v.match(/(klassen_id|workgroup_id)=(\d+)/);
    if (!m) return null;
    const t = o.textContent.trim().replace(/\s+/g, ' ');
    const [name, ...rest] = t.split(' - ');
    const [bezeichnung = '', klassenlehrperson = ''] = rest.join(' - ').split(' – ');
    return {
      id: +m[2],
      typ: m[1] === 'klassen_id' ? 'Klasse' : 'Arbeitsgruppe',
      gruppe: o.parentElement.getAttribute('label') || '',
      name: name || '',
      bezeichnung,
      klassenlehrperson
    };
  }).filter(Boolean);

  // 2) Fächer + 3) Räume: Bearbeitungsansicht einer bestehenden Lektion öffnen und wieder schliessen
  const cell = { classOrWorkgroupId: refClassId, schoolYear: 0, semester: 1, dayCode: refDay, lessonId: refLesson, classOrWorkgroupMode: 'class' };
  const ed = dom(await post(TT, { ...cell, type: 1 }));
  await post(TT, { ...cell, type: 3 });

  const faecher = [...ed.querySelectorAll('select[id^=tt_select_] option')]
    .filter(o => +o.value > 0 && o.value !== '99999')
    .map(o => {
      const m = o.textContent.trim().match(/^(.*)\(([^)]+)\)$/);
      return { id: +o.value, kuerzel: m ? m[2] : '', name: (m ? m[1] : o.textContent).trim() };
    });

  const raeume = [...ed.querySelectorAll('select[id^=room_id_] option')]
    .filter(o => +o.value > 0)
    .map(o => {
      const t = o.textContent.trim().replace(/\t/g, ' ');
      const m = t.match(/^(.*?)\s*\[([^\]]+)\]$/);
      const name = m ? m[1] : t;
      const p = name.split(' - ');
      return { id: +o.value, kuerzel: m ? m[2] : '', geschoss: p[0] || '', nummer: p[1] || '', bezeichnung: p.slice(2).join(' - '), name };
    });

  // 4) Lehrpersonen: Personenverwaltung, Kategorie "lehrperson", pro Schuleinheit
  const lp = new Map();
  for (const unit of schoolUnits) {
    const h = await post('inc/ajax/persons/show_persons_of_group.php', {
      pageRequest: 154, personCategory: 'lehrperson', schoolclassId: 'null', workgroupId: 'null',
      schoolUnitId: unit, schoolYear: 0, searchMode: 0
    });
    if (h.length < 100) continue; // "Es ist ein Fehler aufgetreten." = Einheit existiert nicht
    dom(h).querySelectorAll('li[id^=li_]').forEach(li => {
      const id = +li.id.slice(3);
      const nachname = ((li.querySelector('[id^=name_person_]') || {}).textContent || '').trim();
      const vorname = ((li.querySelector('[id^=vorname_person_]') || {}).textContent || '').trim();
      if (!lp.has(id)) lp.set(id, { id, nachname, vorname, kuerzel: nachname.slice(0, 2) + vorname.slice(0, 2), schuleinheiten: [] });
      lp.get(id).schuleinheiten.push(unit === 1 ? 'Hinterbirch' : unit === 2 ? 'Mettmenriet' : 'Einheit ' + unit);
    });
  }
  const lehrpersonen = [...lp.values()].sort((a, b) => (a.nachname + a.vorname).localeCompare(b.nachname + b.vorname, 'de'));

  // aktive Klasse in der Session wieder auf die Referenzklasse setzen
  await get('admin.php?page_request=6&klassen_id=' + refClassId);

  return { stand: new Date().toISOString(), klassen, faecher, raeume, lehrpersonen };
}

function escolaDownload(daten) {
  const csv = rows => {
    if (!rows.length) return '';
    const cols = Object.keys(rows[0]);
    const esc = v => { const s = Array.isArray(v) ? v.join(', ') : String(v ?? ''); return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    return '﻿' + [cols.join(';'), ...rows.map(r => cols.map(c => esc(r[c])).join(';'))].join('\n');
  };
  const dl = (name, text, type) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name; a.click();
  };
  const d = daten.stand.slice(0, 10);
  dl(`escola_klassen_${d}.csv`, csv(daten.klassen), 'text/csv');
  dl(`escola_faecher_${d}.csv`, csv(daten.faecher), 'text/csv');
  dl(`escola_raeume_${d}.csv`, csv(daten.raeume), 'text/csv');
  dl(`escola_lehrpersonen_${d}.csv`, csv(daten.lehrpersonen), 'text/csv');
  dl(`escola_stammdaten_${d}.json`, JSON.stringify(daten, null, 2), 'application/json');
}
