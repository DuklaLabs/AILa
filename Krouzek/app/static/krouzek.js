const BASE = window.BASE_PATH || "";
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isAsset = id => typeof id === "string" && id.length > 0;
const coll = new Intl.Collator("cs");
const STATES = ["u", "p", "a", "x"];
const STATE_LABEL = { p: "Přítomen", a: "Nepřítomen", u: "Nezapsáno", x: "Nenastoupil" };
const STATE_MARK = { p: "✓", a: "✕", u: "", x: "–" };
const STATUS = { idea: "Nápad", run: "Probíhá", pause: "Pozastaveno", done: "Hotovo" };
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
let today = iso(new Date());   // refreshed every minute, so a page left open overnight moves to the new day
// school year runs September–June; SY is its starting calendar year (2026 = 2026/2027)
const FIRST_SY = 2026;
const defaultSY = () => { const d = new Date(); return d.getMonth() >= 7 ? d.getFullYear() : d.getFullYear() - 1; };
let SY = defaultSY();
try { const s = +localStorage.getItem("kruzek-year"); if (s >= FIRST_SY && s <= defaultSY() + 1) SY = s; } catch {}
let YEAR_FROM, YEAR_TO;
const setYearRange = () => { YEAR_FROM = new Date(SY, 8, 1); YEAR_TO = new Date(SY + 1, 5, 30); };
setYearRange();
const yearLabel = () => `${SY}/${SY + 1}`;
const inYear = date => date >= iso(YEAR_FROM) && date <= iso(new Date(SY + 1, 7, 31));
const projYear = p => p.year ?? FIRST_SY;

/* two groups (ZŠ, SŠ) with their own students, sessions, projects and cancelled days; contacts are shared */
// name: label in PDFs; forName: after "Kroužek pro …" (SŠ is a single school)
const GROUP = { zs: { name: "základní školy", forName: "základní školy", short: "ZŠ", day: 5, start: "14:00", end: "16:00" }, ss: { name: "střední škola", forName: "střední školu", short: "SŠ", day: 2, start: "13:30", end: "15:30", dropIn: true } };
// SŠ students come when they can: attendance is only "came" or blank, no absences or percentages; they have a class and class teacher instead of parent contacts
const drop = () => !!GROUP[G].dropIn;
const clsKey = c => { const m = String(c || "").match(/^(\d+)\.?\s*(.*)$/); return m ? [+m[1], m[2]] : [99, String(c || "")]; };
const byCls = (a, b) => { const x = clsKey(a), y = clsKey(b); return x[0] - y[0] || coll.compare(x[1], y[1]); };
const clsTag = s => drop() && s.cls ? `<span class="cls">${esc(s.cls)}</span>` : "";
const lbl = k => drop() ? ({ p: "Přišel", u: "Nebyl" }[k] || STATE_LABEL[k]) : STATE_LABEL[k];
const cellCls = v => drop() && v !== "p" ? "n" : v;
// "family" holds student and parent contacts; its access rule lets only admins read it
const GCOLS = ["students", "sessions", "projects", "cancelled", "family"];
const D = {};
for (const g in GROUP) D[g] = { students: new Map(), sessions: new Map(), projects: new Map(), cancelled: new Map(), family: new Map(), weekday: null, start: null, end: null };
let G = "zs";
try { const s = localStorage.getItem("kruzek-group"); if (GROUP[s]) G = s; } catch {}
const S = { contacts: new Map(), loaded: new Set(), got: new Set() };
GCOLS.forEach(k => Object.defineProperty(S, k, { get: () => D[G][k] }));
const colName = (g, k) => g === "zs" ? k : g + "_" + k;
const gpath = p => { const c = p.split("/")[0]; return GCOLS.includes(c) ? colName(G, c) + p.slice(c.length) : p; };
const DAY = ["neděle", "pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota"];
const DAY_SHORT = ["ne", "po", "út", "st", "čt", "pá", "so"];
const DAYS_PL = ["neděle", "pondělky", "úterky", "středy", "čtvrtky", "pátky", "soboty"];
const EACH = ["každou neděli", "každé pondělí", "každé úterý", "každou středu", "každý čtvrtek", "každý pátek", "každou sobotu"];
// regular slots per group: [{day, start, end}], several per week allowed; older settings stored one weekday + times
const slots = () => {
  const g = D[G];
  if (Array.isArray(g.slots)) return [...g.slots].sort((a, b) => ((a.day + 6) % 7) - ((b.day + 6) % 7) || a.start.localeCompare(b.start));
  return [{ day: g.weekday ?? GROUP[G].day, start: g.start || GROUP[G].start, end: g.end || GROUP[G].end }];
};
const dow = isoDate => new Date(isoDate + "T12:00").getDay();
const slotFor = day => slots().find(s => s.day === day);
const isRegular = day => !!slotFor(day);
const slotTime = s => `${s.start}–${s.end}`;
const tStart = date => (slotFor(dow(date)) || slots()[0])?.start || GROUP[G].start;
const tEnd = date => (slotFor(dow(date)) || slots()[0])?.end || GROUP[G].end;
const sessTime = (s, date = s?.date) => s?.start && s?.end ? `${s.start}–${s.end}` : `${tStart(date)}–${tEnd(date)}`;
const slotsShort = () => slots().map(s => `${DAY_SHORT[s.day]} ${slotTime(s)}`).join(", ");
const saveSlots = list => { D[G].slots = list; render(); return write("settings/" + G, d => d.set({ slots: list })); };
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const dayName = isoDate => DAY[new Date(isoDate + "T12:00").getDay()];
const CTYPE = { teacher: "Vyučující", school: "Škola", parent: "Rodiče", other: "Další kontakty" };
let db = null, canWrite = true;

function fmtDate(iso, long) {
  const [y, m, d] = iso.split("-").map(Number);
  return long ? `${d}. ${m}. ${y}` : `${d}. ${m}.`;
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => t.hidden = true, 2600);
}
function slug(s) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "x";
}
const bySurname = (a, b) => coll.compare(a.surname, b.surname) || coll.compare(a.first, b.first);
// active students drive attendance and stats; inactive ones stay in the roster and history
const allStudents = () => [...S.students.values()].sort(bySurname);
const students = () => allStudents().filter(s => !s.inactive);
// sessions and projects of the selected school year (students carry over between years)
const sessions = () => [...S.sessions.values()].filter(s => inYear(s.date)).sort((a, b) => a.date.localeCompare(b.date));
const projects = () => [...S.projects.values()].filter(p => projYear(p) === SY);
// a meeting counts as held only once its end time has passed
const nowHM = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
const isOver = (date, s) => date < today || (date === today && nowHM() >= (s?.end || tEnd(date)));
const past = () => sessions().filter(s => isOver(s.date, s));

// one write at a time per document
const queues = new Map();
function write(path, fn) {
  if (!db) { toast("Data teď nejdou uložit."); return Promise.resolve(); }
  path = gpath(path);
  const prev = queues.get(path) || Promise.resolve();
  const before = snapshotOf(path);
  let op = null;
  const next = prev.then(() => {
    // record which operation ran, so the change history can describe and undo it
    const ref = db.doc(path);
    return fn({ set: x => (op = "set", ref.set(x)), update: x => (op = "update", ref.update(x)), delete: () => (op = "delete", ref.delete()) });
  }).then(() => logHistory(path, before, op)).catch(e => {
    if (e?.code === "invalid_argument" && !canWrite) return;
    if (e?.code === "invalid_argument") { canWrite = false; applyRO(); toast("Úpravy nejsou pro tvůj účet povolené."); return; }
    toast(e?.code === "quota_exceeded" ? "Úložiště je plné, smaž nějaké staré záznamy." : "Uložení se nepovedlo, zkus to znovu.");
  });
  queues.set(path, next);
  return next;
}

/* ---------- change history (admins only) ---------- */
// the document's state just before a write: null when it did not exist, undefined when not tracked
function snapshotOf(path) {
  const [c, id] = path.split("/");
  let map = c === "contacts" ? S.contacts : null;
  for (const g in GROUP) for (const k of GCOLS) if (colName(g, k) === c) map = D[g][k];
  if (!map) return undefined;
  const d = map.get(id);
  if (!d) return null;
  const { id: _, ...rest } = d;
  return JSON.parse(JSON.stringify(rest));
}
function histLabel(path, before) {
  const [c, id] = path.split("/"), base = c.replace(/^ss_/, ""), grp = c.startsWith("ss_") ? "SŠ" : "ZŠ";
  const g = c.startsWith("ss_") ? "ss" : "zs", cur = (base !== "contacts" && D[g][base]?.get(id)) || {};
  const doc = before || cur, stu = D[g].students.get(id) || doc;
  switch (base) {
    case "students": return `Student ${doc.surname || ""} ${doc.first || ""} (${grp})`;
    case "family": return `Kontakty žáka ${stu.surname || id} (${grp})`;
    case "sessions": return `Schůzka ${fmtDate(id, true)} (${grp})`;
    case "cancelled": return `Odpadlý termín ${fmtDate(id, true)} (${grp})`;
    case "projects": return `Projekt ${doc.name || ""} (${grp})`;
    case "contacts": return `Kontakt ${(before || S.contacts.get(id) || {}).name || ""}`;
    default: return path;
  }
}
const histLast = new Map();
function logHistory(path, before, op) {
  if (before === undefined || !op || !db) return;
  // many quick edits of one document (clicking attendance cells) collapse into one entry
  const now = Date.now(), last = histLast.get(path);
  if (last && now - last < 90000 && op !== "delete") return;
  histLast.set(path, now);
  return db.collection("history").doc().set({ at: now, path, op, before, label: histLabel(path, before) }).catch(() => {});
}
const OP_WORD = { set: before => before ? "Změněno" : "Přidáno", update: () => "Změněno", delete: () => "Smazáno" };
async function openHistory() {
  if (!db || !canWrite) return;
  $("#histList").innerHTML = `<p class="hint">Načítám…</p>`;
  $("#dlgHist").showModal();
  try {
    const snap = await db.collection("history").orderBy("at", "desc").limit(150).get();
    const rows = snap.docs.map(d => ({ hid: d.id, ...d.data() }));
    $("#histList").innerHTML = rows.length ? rows.map(h => {
      const dt = new Date(h.at), when = `${dt.getDate()}. ${dt.getMonth() + 1}. ${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}`;
      return `<div class="histrow${h.undone ? " done" : ""}"><time>${when}</time><span><b>${(OP_WORD[h.op] || (() => "Změněno"))(h.before)}</b> · ${esc(h.label || h.path)}</span>
        ${h.undone ? `<span class="hint">vráceno</span>` : `<button class="btn" type="button" data-undo="${h.hid}">Vrátit</button>`}</div>`;
    }).join("") : `<p class="hint">Zatím žádné změny.</p>`;
    $("#histList")._rows = rows;
  } catch { $("#histList").innerHTML = `<p class="hint">Historii se nepodařilo načíst.</p>`; }
}
// undo = put the document back exactly as it was before that change
$("#histList").addEventListener("click", async e => {
  const b = e.target.closest("[data-undo]"); if (!b) return;
  const h = ($("#histList")._rows || []).find(x => x.hid === b.dataset.undo); if (!h) return;
  if (!b.classList.contains("armed")) { b.classList.add("armed"); b.textContent = "Opravdu vrátit?"; return; }
  b.disabled = true;
  try {
    const ref = db.doc(h.path);
    if (h.before) await ref.set(h.before); else await ref.delete();
    await db.doc("history/" + h.hid).update({ undone: true });
    toast("Vráceno: " + (h.label || h.path)); openHistory();
  } catch { b.disabled = false; toast("Vrácení se nepovedlo."); }
});

function stats(id) {
  let p = 0, n = 0, last = null;
  if (drop()) {
    for (const s of past()) { n++; if (s.att?.[id] === "p") { p++; last = s.date; } }
    return { p, n, pct: null, last };
  }
  for (const s of past()) {
    const st = s.att?.[id] || "u";
    if (st === "x") continue;
    n++; if (st === "p") p++;
  }
  return { p, n, pct: n ? Math.round(p / n * 100) : null };
}

/* ---------- views ---------- */
const ready = () => S.got.has(G + ":students") && S.got.has(G + ":sessions");
const sk = (n, h, extra = "") => Array.from({ length: n }, () => `<div class="sk" style="height:${h}px;${extra}"></div>`).join("");

// next Friday is plain date math, so the hero is complete even before data loads
function renderHero() {
  // next meeting: a planned session or the regular weekday, skipping cancelled days
  const d = new Date(); d.setHours(0, 0, 0, 0);
  let k = iso(d);
  for (let i = 0; i < 400; i++, d.setDate(d.getDate() + 1), k = iso(d)) {
    const sx = S.sessions.get(k);
    if ((sx && !isOver(k, sx)) || (!sx && isRegular(d.getDay()) && !S.cancelled.has(k) && !isOver(k))) break;
  }
  const days = Math.round((d - new Date(new Date().setHours(0, 0, 0, 0))) / 864e5);
  $("#heroDate").textContent = days === 0 ? `Dnes · ${DAY[d.getDay()]} ${fmtDate(k, true)}` : `${cap(DAY[d.getDay()])} ${fmtDate(k, true)}`;
  const next = S.sessions.get(k), topic = next?.topic;
  $("#heroSub").textContent = `${sessTime(next, k)} · ` + (topic ? "Téma: " + topic : isRegular(d.getDay()) ? EACH[d.getDay()] : "mimořádná schůzka");
  $("#heroEyebrow").textContent = "Další kroužek · " + GROUP[G].short;
  $("#brandSub").textContent = `Kroužek pro ${GROUP[G].forName} · ${slotsShort()}`;
  // dnes / zítra / zbývá N dny|dnů
  const many = days >= 2;
  $("#heroDays").textContent = days === 0 ? "dnes" : days === 1 ? "zítra" : days;
  $("#heroDays").classList.toggle("word", !many);
  $("#heroDaysPre").hidden = !many;
  $("#heroDaysLbl").hidden = days === 1;
  $("#heroDaysLbl").textContent = days < 5 ? "dny" : "dnů";
  // today: how long until it starts, or how long it still runs
  if (days === 0) {
    const toMin = t => +t.slice(0, 2) * 60 + +t.slice(3, 5), dur = m => m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;
    const now = toMin(nowHM()), st = toMin(next?.start || tStart(k)), en = toMin(next?.end || tEnd(k));
    if (now < st) $("#heroDaysLbl").textContent = "za " + dur(st - now);
    else { $("#heroDays").textContent = "probíhá"; $("#heroDaysLbl").textContent = "ještě " + dur(en - now); }
  }
}

function renderTiles() {
  if (!ready()) { $("#tiles").innerHTML = sk(5, 104); return; }
  const st = students(), ps = past(), pr = projects();
  const counts = ps.map(s => Object.values(s.att || {}).filter(v => v === "p").length);
  const avg = counts.length ? (counts.reduce((a, b) => a + b, 0) / counts.length) : 0;
  const active = pr.filter(p => p.status === "run").length;
  $("#tiles").innerHTML = `
    <div class="tile"><span class="k">Studentů</span><span class="v num">${st.length}</span><span class="s">v seznamu kroužku</span></div>
    <div class="tile"><span class="k">Proběhlo schůzek</span><span class="v num">${ps.length}</span><span class="s">${ps.length ? "od " + fmtDate(ps[0].date, true) : "zatím žádná"}</span></div>
    <div class="tile"><span class="k">Odpadlo schůzek</span><span class="v num">${fridays().filter(f => f.state === "off").length}</span><span class="s">${fridays().filter(f => f.state === "missing").length ? fridays().filter(f => f.state === "missing").length + " bez záznamu" : "vše zapsáno"}</span></div>
    <div class="tile"><span class="k">Průměrně přítomno</span><span class="v num">${avg.toFixed(1).replace(".", ",")}</span><span class="s">studentů na schůzku</span></div>
    <div class="tile"><span class="k">Projekty</span><span class="v num">${active}<small style="font-size:16px;color:var(--muted)"> / ${pr.length}</small></span><span class="s">probíhá / celkem</span></div>`;
}

function renderChart() {
  if (!ready()) { $("#chart").innerHTML = `<div style="display:flex;align-items:end;gap:14px;height:200px">${[60, 85, 70, 95, 40].map(h => `<div class="sk" style="flex:1;height:${h}%"></div>`).join("")}</div>`; return; }
  const ss = sessions(), max = Math.max(students().length, 1);
  if (!ss.length) { $("#chart").innerHTML = `<p class="hint">Zatím žádné schůzky.</p>`; return; }
  const W = 560, H = 230, L = 30, B = 34, T = 18, R = 8;
  const bw = (W - L - R) / ss.length, y = v => T + (H - T - B) * (1 - v / max);
  const step = max > 10 ? 5 : 2;
  let g = "";
  for (let v = 0; v <= max; v += step) g += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  ss.forEach((s, i) => {
    const c = Object.values(s.att || {}).filter(v => v === "p").length, fut = !isOver(s.date, s);
    const x = L + i * bw + bw * .18, w = bw * .64, h = fut ? (H - T - B) : (y(0) - y(c));
    g += `<g><title>${fmtDate(s.date, true)}: ${fut ? "plánováno" : c + " přítomno"}</title>
      <rect class="bar${fut ? " future" : ""}" x="${x}" y="${fut ? T : y(c)}" width="${w}" height="${Math.max(h, 0)}" rx="6"/>
      ${fut ? `<text x="${x + w / 2}" y="${T + 16}" text-anchor="middle">plán</text>` : `<text class="val" x="${x + w / 2}" y="${y(c) - 5}" text-anchor="middle">${c}</text>`}
      <text x="${x + w / 2}" y="${H - 12}" text-anchor="middle">${fmtDate(s.date)}</text></g>`;
  });
  $("#chart").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Počet přítomných na jednotlivých schůzkách">${g}</svg>`;
}

function renderRank() {
  if (!ready()) { $("#rank").innerHTML = sk(6, 26, "border-radius:8px"); return; }
  $("#rankTitle").textContent = drop() ? "Kdo chodí nejčastěji" : "Docházka studentů";
  if (drop()) {
    const rows = students().map(s => ({ s, ...stats(s.id) })).filter(r => r.p).sort((a, b) => b.p - a.p || bySurname(a.s, b.s));
    const max = Math.max(1, ...rows.map(r => r.p));
    $("#rank").innerHTML = rows.length ? rows.map(r => `<li><span><b>${esc(r.s.surname)}</b> ${esc(r.s.first)} ${clsTag(r.s)}</span><span class="num">${r.p}×</span><span class="bar"><i style="width:${r.p / max * 100}%"></i></span></li>`).join("") : `<li class="hint">Až někdo přijde, ukáže se tady.</li>`;
    return;
  }
  const rows = students().map(s => ({ s, ...stats(s.id) })).filter(r => r.n).sort((a, b) => b.pct - a.pct || coll.compare(a.s.surname, b.s.surname));
  $("#rank").innerHTML = rows.length ? rows.map(r => `<li><span><b>${esc(r.s.surname)}</b> ${esc(r.s.first)}</span><span class="num">${r.p}/${r.n}</span><span class="bar"><i style="width:${r.pct}%"></i></span></li>`).join("") : `<li class="hint">Docházka se ukáže po první schůzce.</li>`;
}

function renderMiniProjects() {
  if (!ready()) { $("#miniProjects").innerHTML = sk(2, 40, "margin-bottom:10px;border-radius:10px"); return; }
  const pr = projects().filter(p => p.status !== "done").sort((a, b) => coll.compare(a.name, b.name));
  $("#miniProjects").innerHTML = pr.length ? `<div class="rank">${pr.map(p => `<li style="list-style:none"><span><b>${esc(p.name)}</b> <span class="pill st-${p.status}">${STATUS[p.status]}</span></span><span class="num">${p.progress || 0} %</span><span class="progress bar" style="height:8px"><i style="width:${p.progress || 0}%"></i></span></li>`).join("")}</div>`
    : `<div class="empty"><b>Zatím žádné projekty</b><span>Přidej první projekt, třeba to, na čem tým právě pracuje.</span><button class="btn primary" type="button" data-go="new-project">Nový projekt</button></div>`;
}

function renderMatrix() {
  const st = students(), ss = sessions();
  if (!st.length) { $("#matrix").innerHTML = `<div class="empty"><b>Žádní studenti</b><span>Přidej je v sekci Studenti.</span></div>`; return; }
  const D_ = drop();
  $("#attHint").textContent = D_ ? "Studenti chodí, kdy můžou. Klikni na políčko u toho, kdo přišel; prázdné políčko znamená, že tu nebyl. Kliknutím na datum otevřeš celou schůzku." : "Kliknutím na políčko měníš stav. Kliknutím na datum otevřeš celou schůzku s poznámkami.";
  $("#attLegend").innerHTML = D_ ? `<span><i class="dot s-p"></i>Přišel</span><span><i class="dot s-n"></i>Nebyl</span><span><i class="dot" style="--c:var(--accent);--cs:var(--accent);border-radius:50%;width:10px;height:10px"></i>Poznámka</span>`
    : `<span><i class="dot s-p"></i>Přítomen</span><span><i class="dot s-a"></i>Nepřítomen</span><span><i class="dot s-u"></i>Nezapsáno</span><span><i class="dot s-x"></i>Ještě nenastoupil</span><span><i class="dot" style="--c:var(--accent);--cs:var(--accent);border-radius:50%;width:10px;height:10px"></i>Poznámka</span>`;
  const head = ss.map(s => { const fut = !isOver(s.date, s); return `<th class="${fut ? "future" : ""}"><button class="colhead" type="button" data-sess="${s.id}"><b>${fmtDate(s.date)}</b><small>${fut ? "plán" : esc((s.topic || "").slice(0, 14))}</small></button></th>`; }).join("");
  const body = st.map(s => {
    const r = stats(s.id);
    const cells = ss.map(x => {
      const v = x.att?.[s.id] || "u", note = x.notes?.[s.id];
      return `<td><button class="cell s-${cellCls(v)}${note ? " note" : ""}" type="button" data-cell="${x.id}|${s.id}" title="${esc(fmtDate(x.date, true) + " · " + lbl(v) + (note ? " · " + note : ""))}" aria-label="${esc(s.surname + " " + s.first + ", " + fmtDate(x.date, true) + ": " + lbl(v))}" ${canWrite ? "" : "disabled"}>${D_ ? (v === "p" ? "✓" : "") : STATE_MARK[v]}</button></td>`;
    }).join("");
    return `<tr><td class="name"><b>${esc(s.surname)}</b> <span>${esc(s.first)}</span>${s.nick ? `<span class="nick">${esc(s.nick)}</span>` : ""}${clsTag(s)}</td>${cells}${D_ ? `<td class="pct" style="color:${r.p ? "var(--p)" : "var(--muted)"}">${r.p}×</td></tr>` : `<td class="pct" style="color:${r.pct == null ? "var(--muted)" : r.pct >= 75 ? "var(--p)" : r.pct >= 50 ? "var(--u)" : "var(--a)"}">${r.pct == null ? "—" : r.pct + " %"}</td></tr>`}`;
  }).join("");
  const foot = ss.map(x => `<td>${Object.values(x.att || {}).filter(v => v === "p").length}</td>`).join("");
  $("#matrix").innerHTML = `<table class="matrix"><thead><tr><th class="name">Student</th>${head}<th>${D_ ? "Přišel" : "Účast"}</th></tr></thead><tbody>${body}</tbody><tfoot><tr><td class="name">${D_ ? "Přišlo celkem" : "Přítomno celkem"}</td>${foot}<td></td></tr></tfoot></table>`;
}

function renderProjects() {
  const pr = projects().sort((a, b) => ["run", "pause", "idea", "done"].indexOf(a.status) - ["run", "pause", "idea", "done"].indexOf(b.status) || coll.compare(a.name, b.name));
  if (!pr.length) {
    $("#projects").innerHTML = `<div class="empty"><b>Zatím žádné projekty</b><span>Ke každému projektu zapíšeš stav, kolik je hotovo, kdo v týmu dělá co a jak práce postupuje.</span>${canWrite ? `<button class="btn primary" type="button" data-go="new-project">Přidat první projekt</button>` : ""}</div>`;
    return;
  }
  $("#projects").innerHTML = `<div class="cards">${pr.map(p => {
    const team = (p.members || []).map(m => { const s = S.students.get(m.id); return s ? `<span class="chip"><b>${esc(s.surname)}</b> ${esc(s.first)}${m.role ? ` <em>· ${esc(m.role)}</em>` : ""}</span>` : ""; }).join("");
    const log = [...(p.log || [])].sort((a, b) => b.date.localeCompare(a.date));
    return `<article class="card">
      <div class="row"><span class="pill st-${p.status}">${STATUS[p.status] || "Nápad"}</span><span class="num" style="margin-left:auto;font-weight:600">${p.progress || 0} %</span></div>
      <h3>${esc(p.name)}</h3>
      <div class="progress"><i style="width:${p.progress || 0}%"></i></div>
      ${p.desc ? `<p class="desc">${esc(p.desc)}</p>` : ""}
      <div class="chips">${team || `<span class="hint">Tým zatím není přiřazený.</span>`}</div>
      <div><div class="hint" style="margin-bottom:6px;font-weight:600">Průběh</div>
        ${log.length ? `<ul class="log">${log.slice(0, 5).map(l => `<li><time>${fmtDate(l.date, true)}</time>${esc(l.text)}${isAsset(l.photo) ? `<a href="${l.photo}" target="_blank" rel="noopener" title="Otevřít fotku"><img class="photo" src="${l.photo}" alt="Fotka z ${fmtDate(l.date, true)}" loading="lazy"></a>` : ""}</li>`).join("")}</ul>` : `<p class="hint">Zatím žádný záznam.</p>`}
      </div>
      ${canWrite ? `<form class="logadd" data-log="${p.id}"><input type="text" id="log-${p.id}" placeholder="Co se dnes udělalo…"><label class="cam" title="Přidat fotku"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h3l2-3h6l2 3h3a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="4"/></svg><input type="file" id="photo-${p.id}" accept="image/*" aria-label="Přidat fotku"></label><button class="btn" type="submit">Zapsat</button></form>
      <div class="row"><button class="btn" type="button" data-edit-project="${p.id}">Upravit projekt</button></div>` : ""}
    </article>`;
  }).join("")}</div>`;
}

function renderRoster() {
  const st = [...students(), ...allStudents().filter(s => s.inactive)], ss = past();
  $("#rosterHint").textContent = drop() ? "Rozdělení podle tříd, v každé podle příjmení. Kliknutím upravíš třídu, třídního učitele, roli a poznámku." : "Seřazeno podle příjmení. Kliknutím upravíš roli a poznámku.";
  ["#parentPdf"].forEach(x => $(x).hidden = drop());
  if (!st.length) { $("#roster").innerHTML = `<div class="empty"><b>Žádní studenti</b><span>Přidej prvního studenta.</span></div>`; return; }
  const card = s => {
    if (!drop()) return rosterCard(s, ss);
    const r = stats(s.id);
    const projs = projects().filter(p => (p.members || []).some(m => m.id === s.id)).map(p => esc(p.name));
    return `<button class="stu${s.inactive ? " off" : ""}" type="button" data-card="${s.id}">
      <div class="nm"><b>${esc(s.surname)}</b> <span>${esc(s.first)}</span>${s.nick ? ` <span class="nick">„${esc(s.nick)}“</span>` : ""}${s.inactive ? ` <span class="pill st-idea">neaktivní</span>` : ""}</div>
      <div class="teach">${s.cls ? `<span class="cls">${esc(s.cls)}</span> ` : ""}${s.teacher ? "třídní: " + esc(s.teacher) : s.cls ? "" : "Třída zatím není vyplněná"}</div>
      ${s.role ? `<div class="role">${esc(s.role)}</div>` : ""}
      <div class="visits"><b class="num">${r.p}×</b><small>${r.p ? "na kroužku · naposledy " + fmtDate(r.last, true) : "zatím nepřišel"}</small></div>
      ${ss.length ? `<div class="strip">${ss.map(x => `<i class="s-${x.att?.[s.id] === "p" ? "p" : "n"}" title="${fmtDate(x.date, true)}: ${x.att?.[s.id] === "p" ? "přišel" : "nebyl"}"></i>`).join("")}</div>` : ""}
      ${projs.length ? `<div class="hint">Projekty: ${projs.join(", ")}</div>` : ""}
      ${s.note ? `<p class="note">${esc(s.note)}</p>` : ""}
    </button>`;
  };
  if (drop()) {
    const groups = new Map();
    st.forEach(s => { const k = s.cls || ""; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(s); });
    const keys = [...groups.keys()].sort((a, b) => (!a) - (!b) || byCls(a, b));
    $("#roster").style.display = "block";
    $("#roster").innerHTML = keys.map(k => {
      const list = groups.get(k), teachers = [...new Set(list.map(s => s.teacher).filter(Boolean))];
      return `<div class="clsgrp"><h3>${k ? `<span class="cls" style="font-size:14px">${esc(k)}</span>` : "Bez třídy"} <small>${teachers.length ? "třídní: " + teachers.map(esc).join(", ") + " · " : ""}${list.length} ${list.length === 1 ? "student" : list.length < 5 ? "studenti" : "studentů"}</small></h3><div class="roster">${list.map(card).join("")}</div></div>`;
    }).join("");
    return;
  }
  $("#roster").style.display = "";
  $("#roster").innerHTML = st.map(card).join("");
}
function rosterCard(s, ss) {
  {
    const r = stats(s.id), C = 2 * Math.PI * 18, pct = r.pct ?? 0;
    const projs = projects().filter(p => (p.members || []).some(m => m.id === s.id)).map(p => esc(p.name));
    const ph = S.family.get(s.id)?.photo;
    return `<button class="stu${s.inactive ? " off" : ""}" type="button" data-card="${s.id}">
      ${isAsset(ph) ? `<span class="avatar-sm"><img src="${ph}" alt="" loading="lazy"></span>` : ""}
      <div class="nm"><b>${esc(s.surname)}</b> <span>${esc(s.first)}</span>${s.nick ? ` <span class="nick">„${esc(s.nick)}“</span>` : ""}${s.inactive ? ` <span class="pill st-idea">neaktivní</span>` : ""}</div>
      <div class="role">${esc(s.role || "")}</div>
      <div class="ring"><svg width="44" height="44" viewBox="0 0 44 44"><circle class="bg" cx="22" cy="22" r="18"/><circle class="fg" cx="22" cy="22" r="18" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct / 100)}" transform="rotate(-90 22 22)"/></svg>
        <div><b class="num">${r.pct == null ? "—" : r.pct + " %"}</b><br><small>${r.p} z ${r.n} schůzek</small></div></div>
      <div class="strip">${ss.map(x => `<i class="s-${x.att?.[s.id] || "u"}" title="${fmtDate(x.date, true)}: ${STATE_LABEL[x.att?.[s.id] || "u"]}"></i>`).join("")}</div>
      ${projs.length ? `<div class="hint">Projekty: ${projs.join(", ")}</div>` : ""}
      ${s.note ? `<p class="note">${esc(s.note)}</p>` : ""}
    </button>`;
  }
}

/* every Friday of the school year with its state */
function fridays() {
  const first = sessions()[0]?.date;
  // meeting days: the regular weekday plus any day with a session or a cancellation
  const out = [], d = new Date(YEAR_FROM);
  for (; d <= YEAR_TO; d.setDate(d.getDate() + 1)) {
    const k = iso(d), sess = S.sessions.get(k), off = S.cancelled.get(k);
    if (!isRegular(d.getDay()) && !sess && !off) continue;
    let state;
    if (sess) state = isOver(k, sess) ? "held" : "planned";
    else if (off) state = "off";
    else if (!isOver(k)) state = "future";
    else if (!first || k < first) state = "pre";
    else state = "missing";
    out.push({ date: k, state, sess, off });
  }
  return out;
}
const FSTATE = { held: "Proběhlo", off: "Odpadlo", missing: "Chybí záznam", future: "Budoucí termín", planned: "Naplánovaná schůzka", pre: "Před zahájením kroužku" };

function renderCalendar() {
  const fr = fridays(), byDate = new Map(fr.map(f => [f.date, f]));
  const n = s => fr.filter(f => f.state === s).length;
  $("#calsum").innerHTML = `
    <span class="k s-p"><i class="dot"></i><b class="num">${n("held")}</b> proběhlo</span>
    <span class="k s-a"><i class="dot"></i><b class="num">${n("off")}</b> odpadlo</span>
    <span class="k s-u"><i class="dot"></i><b class="num">${n("missing")}</b> chybí záznam</span>
    <span class="k"><b class="num">${n("future") + n("planned")}</b> termínů do konce roku</span>`;
  $("#slots").innerHTML = slots().map((s, i) => `<button type="button" class="slot" data-slot="${i}" ${canWrite ? "" : "disabled"}><b>${cap(DAY[s.day])}</b><span class="num">${slotTime(s)}</span></button>`).join("")
    + (canWrite ? `<button type="button" class="slot add" data-slot="new" aria-label="Přidat pravidelný termín">+ Přidat termín</button>` : "");
  $("#calHint").textContent = "Klikni na termín v kalendáři a zapiš, jestli proběhl, nebo proč odpadl. Kliknutím na jiný den přidáš mimořádnou schůzku.";
  let html = "";
  for (let m = new Date(YEAR_FROM); m <= YEAR_TO; m = new Date(m.getFullYear(), m.getMonth() + 1, 1)) {
    const name = m.toLocaleDateString("cs-CZ", { month: "long", year: "numeric" });
    let cells = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"].map((x, i) => `<span class="dn${isRegular((i + 1) % 7) ? " frih" : ""}">${x}</span>`).join("");
    const lead = (m.getDay() + 6) % 7;
    cells += "<span></span>".repeat(lead);
    const days = new Date(m.getFullYear(), m.getMonth() + 1, 0).getDate();
    for (let i = 1; i <= days; i++) {
      const k = iso(new Date(m.getFullYear(), m.getMonth(), i)), f = byDate.get(k);
      if (f) {
        const tip = fmtDate(k, true) + " · " + FSTATE[f.state] + (f.off?.reason ? ": " + f.off.reason : "") + (f.sess?.topic ? " · " + f.sess.topic : "");
        cells += `<button type="button" class="day fri f-${f.state}${k === today ? " today" : ""}" data-fri="${k}" title="${esc(tip)}" aria-label="${esc(tip)}">${i}</button>`;
      } else cells += `<button type="button" class="day free${k === today ? " today" : ""}" data-fri="${k}" title="${esc(cap(dayName(k)) + " " + fmtDate(k, true) + " · přidat mimořádnou schůzku")}" ${canWrite ? "" : "disabled"}>${i}</button>`;
    }
    html += `<div class="month"><h3>${name}</h3><div class="days">${cells}</div></div>`;
  }
  $("#months").innerHTML = html;
  const offs = fr.filter(f => f.state === "off");
  $("#offlist").innerHTML = offs.length ? offs.map(f => `<li><time>${fmtDate(f.date)}</time><span>${esc(f.off.reason || "bez udaného důvodu")}</span></li>`).join("") : `<li class="hint">Zatím nic neodpadlo. Termíny bez záznamu jsou v kalendáři žlutě.</li>`;
}

const ICON_PHONE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>`;
const ICON_COPY = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>`;
const ICON_MAIL = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="3"/><path d="M22 7l-10 6L2 7"/></svg>`;
function renderContacts() {
  const all = [...S.contacts.values()];
  if (!all.length) { $("#contacts").innerHTML = `<div class="empty"><b>Zatím žádné kontakty</b><span>Přidej vyučující, kontakt na školu nebo na rodiče.</span></div>`; return; }
  const initials = n => n.split(/\s+/).filter(Boolean).map(w => w[0]).slice(0, 2).join("").toUpperCase();
  const line = (icon, v, label) => v ? `<div class="line">${icon}<span>${esc(v)}</span><button class="copy" type="button" data-copy="${esc(v)}" aria-label="Kopírovat ${label}" title="Kopírovat">${ICON_COPY}</button></div>` : "";
  // built-in groups first, then custom groups alphabetically, then ungrouped "other"
  const keyOf = c => c.type && c.type !== "other" ? c.type : (c.group ? "g:" + c.group : "other");
  const custom = [...new Set(all.map(keyOf).filter(k => k.startsWith("g:")))].sort((a, b) => coll.compare(a, b));
  const keys = ["teacher", "school", "parent", ...custom, "other"];
  $("#contacts").innerHTML = keys.map(t => {
    const list = all.filter(c => keyOf(c) === t).sort((a, b) => (a.order ?? 99) - (b.order ?? 99) || coll.compare(a.name, b.name));
    if (!list.length) return "";
    return `<div class="cgroup"><h3>${esc(t.startsWith("g:") ? t.slice(2) : CTYPE[t])}</h3><div class="contacts">${list.map(c => `
      <article class="contact">
        <div class="avatar">${esc(initials(c.name))}</div>
        <div class="cn">${esc(c.name)}${c.role ? `<small>${esc(c.role)}</small>` : ""}</div>
        <div class="lines">${line(ICON_PHONE, c.phone, "telefon") + line(ICON_MAIL, c.email, "e-mail") || `<span class="hint">Telefon ani e-mail zatím nejsou vyplněné.</span>`}</div>
        ${c.note ? `<p class="note">${esc(c.note)}</p>` : ""}
        ${canWrite ? `<button class="btn edit" type="button" data-contact="${c.id}">Upravit</button>` : ""}
      </article>`).join("")}</div></div>`;
  }).join("");
}

function renderFamilies() {
  const line = (icon, v, label) => v ? `<div class="line">${icon}<span>${esc(v)}</span><button class="copy" type="button" data-copy="${esc(v)}" aria-label="Kopírovat ${label}" title="Kopírovat">${ICON_COPY}</button></div>` : "";
  const block = (title, p) => {
    const body = (p?.name ? `<div class="pname">${esc(p.name)}</div>` : "") + line(ICON_PHONE, p?.phone, "telefon") + line(ICON_MAIL, p?.email, "e-mail");
    return `<div class="who"><span>${title}</span>${body || `<div class="hint">Nevyplněno</div>`}</div>`;
  };
  // only admins can read family contacts, so the whole section is theirs
  $("#famWrap").hidden = !canWrite;
  if (!canWrite) return;
  const st = allStudents();
  $("#famTitle").textContent = drop() ? "Studenti" : "Žáci a rodiče";
  if (drop()) {
    $("#fam").innerHTML = st.length ? `<div class="fam">${[...st].sort((a, b) => byCls(a.cls, b.cls) || bySurname(a, b)).map(s => { const f = S.family.get(s.id) || {}; return `
    <article class="famcard" id="fam-${s.id}">
      <div class="top"><b>${esc(s.surname)}</b> <span>${esc(s.first)}</span>${clsTag(s)}
        <button class="btn" type="button" data-card="${s.id}">Karta</button><button class="btn" type="button" data-stu="${s.id}">Upravit</button></div>
      <div class="who"><span>Třídní učitel</span>${s.teacher ? `<div class="pname">${esc(s.teacher)}</div>` : `<div class="hint">Nevyplněno</div>`}</div>
      ${block("Student", f.contact)}
    </article>`; }).join("")}</div>` : `<div class="empty"><b>Žádní studenti</b></div>`;
    return;
  }
  $("#fam").innerHTML = st.length ? `<div class="fam">${st.map(s => { const f = S.family.get(s.id) || {}; return `
    <article class="famcard" id="fam-${s.id}">
      <div class="top"><b>${esc(s.surname)}</b> <span>${esc(s.first)}</span>${s.nick ? `<span class="nick">${esc(s.nick)}</span>` : ""}
        <button class="btn" type="button" data-card="${s.id}">Karta</button><button class="btn" type="button" data-stu="${s.id}">Upravit</button></div>
      ${migrBlock(s)}${block("Žák", f.contact)}${block("Rodič 1", f.parent1)}${block("Rodič 2", f.parent2)}
    </article>`; }).join("")}</div>` : `<div class="empty"><b>Žádní studenti</b></div>`;
}
// where a ZŠ student goes to secondary school (entered in the student dialog)
const migrText = s => [s.toSchool, s.toField, s.toYear ? `od ${s.toYear}` : ""].filter(Boolean).join(" · ");
const migrBlock = s => `<div class="who"><span>Střední škola</span>${migrText(s) ? `<div class="pname">${esc(migrText(s))}</div>` : `<div class="hint">Nevyplněno</div>`}</div>`;

function render() {
  renderHero(); renderTiles(); renderChart(); renderRank(); renderMiniProjects(); renderCalendar(); renderMatrix(); renderProjects(); renderRoster(); renderContacts(); renderFamilies();
}

/* ---------- routing ---------- */
const VIEWS = ["prehled", "kalendar", "dochazka", "projekty", "studenti", "kontakty"];
function route() {
  const v = VIEWS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "prehled";
  document.querySelectorAll(".view").forEach(s => s.hidden = s.dataset.v !== v);
  document.querySelectorAll("nav.tabs a").forEach(a => a.dataset.view === v ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  requestAnimationFrame(moveInd);
}
function moveInd() {
  AilaUI.tabs($("#tabbar"));
}
addEventListener("hashchange", route); addEventListener("resize", moveInd);
document.fonts?.ready.then(moveInd);
route();

/* when a meeting ends while the page is open, refresh the counts */
// check the clock often and redraw as soon as the minute changes; browsers slow long timers in
// background tabs, so also catch up the moment the page becomes visible again
let heldCount = -1, lastMinute = "";
function clockTick() {
  if (document.hidden) return;   // nothing to update while nobody is looking
  const t = iso(new Date()), m = nowHM();
  if (t !== today) { today = t; lastMinute = m; render(); return; }
  if (m === lastMinute) return;
  lastMinute = m;
  const n = past().length; if (n !== heldCount) { heldCount = n; render(); } else renderHero();
}
setInterval(clockTick, 5000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) clockTick(); });
addEventListener("focus", clockTick);

/* mark the page as scrolling for a moment so hover effects stay off mid-scroll */
let scrollT;
addEventListener("scroll", () => {
  document.documentElement.classList.add("scrolling");
  clearTimeout(scrollT); scrollT = setTimeout(() => document.documentElement.classList.remove("scrolling"), 150);
}, { passive: true });

/* windows: close by clicking outside or Esc; unsaved edits ask first, attendance saves itself */
function closeDlg(dlg) {
  const form = dlg.querySelector("form"), submit = form?.querySelector('button[type="submit"]:not([hidden])');
  if (dlg.dataset.dirty !== "1" || !submit || !canWrite || dlg.hasAttribute("data-nosave")) return dlg.close();
  if (dlg.id === "dlgSession") return form.requestSubmit(submit);
  if (dlg.querySelector(".ask")) return;
  const bar = document.createElement("div");
  bar.className = "ask";
  bar.innerHTML = `<span>Uložit změny?</span><button class="btn primary" type="button" data-a="save">Uložit</button><button class="btn" type="button" data-a="drop">Zahodit</button><button class="btn" type="button" data-a="back">Zpět</button>`;
  bar.addEventListener("click", e => {
    const a = e.target.closest("[data-a]")?.dataset.a;
    if (a === "save") { bar.remove(); form.requestSubmit(submit); }
    else if (a === "drop") dlg.close();
    else if (a === "back") bar.remove();
  });
  dlg.append(bar); bar.querySelector("button").focus();
}
document.querySelectorAll("dialog").forEach(dlg => {
  dlg.addEventListener("click", e => {
    if (e.target !== dlg) return;
    const r = dlg.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeDlg(dlg);
  });
  dlg.addEventListener("cancel", e => { e.preventDefault(); closeDlg(dlg); });
  dlg.addEventListener("input", () => dlg.dataset.dirty = "1");
  dlg.addEventListener("close", () => { dlg.dataset.dirty = ""; dlg.querySelector(".ask")?.remove(); });
});

/* school year switch: older years stay as an archive, the current one is picked by default */
{
  const sel = $("#yearSel");
  for (let y = defaultSY() + 1; y >= FIRST_SY; y--) sel.insertAdjacentHTML("beforeend", `<option value="${y}">${y}/${y + 1}${y === defaultSY() ? " (letos)" : ""}</option>`);
  sel.value = String(SY);
  sel.addEventListener("change", () => {
    SY = +sel.value; setYearRange();
    try { localStorage.setItem("kruzek-year", String(SY)); } catch {}
    document.querySelectorAll("dialog[open]").forEach(d => d.close());
    render();
    const w = $("main .wrap"); w.classList.remove("flip"); void w.offsetWidth; w.classList.add("flip");
  });
}

/* ZŠ / SŠ switch */
function moveGrpKnob() {
  AilaUI.knob($("#grp"));
}
function setGroup(g, animate) {
  G = g;
  try { localStorage.setItem("kruzek-group", g); } catch {}
  document.querySelectorAll(".grp button").forEach(b => b.setAttribute("aria-pressed", b.dataset.g === g));
  document.querySelectorAll("dialog[open]").forEach(d => d.close());
  moveGrpKnob(); render();
  if (animate) { const w = $("main .wrap"); w.classList.remove("flip"); void w.offsetWidth; w.classList.add("flip"); }
}
$("#grp").addEventListener("click", e => { const b = e.target.closest("button"); if (b && b.dataset.g !== G) setGroup(b.dataset.g, true); });
addEventListener("resize", moveGrpKnob); document.fonts?.ready.then(moveGrpKnob);
setGroup(G, false);

/* regular slot window */
let editSlot = null;
$("#slots").addEventListener("click", e => {
  const b = e.target.closest("[data-slot]"); if (!b || !canWrite) return;
  editSlot = b.dataset.slot === "new" ? null : +b.dataset.slot;
  const s = editSlot == null ? { day: 1, start: GROUP[G].start, end: GROUP[G].end } : slots()[editSlot];
  $("#slotTitle").textContent = editSlot == null ? "Nový pravidelný termín" : "Pravidelný termín";
  $("#slDay").value = String(s.day); $("#slStart").value = s.start; $("#slEnd").value = s.end;
  $("#slDel").hidden = editSlot == null || slots().length < 2;
  armDelete($("#slDel"), () => { saveSlots(slots().filter((_, i) => i !== editSlot)).then(() => toast("Termín odebrán.")); $("#dlgSlot").close(); });
  $("#dlgSlot").showModal();
});
$("#fSlot").addEventListener("submit", e => {
  if (e.submitter?.value === "cancel") return;
  const s = { day: +$("#slDay").value, start: $("#slStart").value, end: $("#slEnd").value };
  if (!s.start || !s.end || s.end <= s.start) { e.preventDefault(); toast("Konec musí být později než začátek."); return; }
  const list = slots().filter((_, i) => i !== editSlot);
  if (list.some(x => x.day === s.day)) { e.preventDefault(); toast(`${cap(DAY[s.day])} už mezi termíny je.`); return; }
  saveSlots([...list, s]).then(() => toast(`Uloženo: ${DAY[s.day]} ${slotTime(s)}`));
});

/* light / dark switch */
function setTheme(mode, save) {
  document.documentElement.dataset.theme = mode;
  $("#theme").dataset.mode = mode;
  $("#theme").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.mode === mode));
  if (save) try { localStorage.setItem("aila-theme", mode); } catch {}
}
let savedTheme = null; try { savedTheme = (localStorage.getItem("aila-theme") || localStorage.getItem("kruzek-theme")); } catch {}
setTheme(savedTheme || document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"), false);
$("#theme").addEventListener("click", e => {
  // a click anywhere on the switch flips the mode; the reveal starts from the target icon
  const mode = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  const b = $(`#theme button[data-mode="${mode}"]`);
  const r0 = b.getBoundingClientRect(), x = r0.left + r0.width / 2, y = r0.top + r0.height / 2;
  if (document.startViewTransition) {
    const t = document.startViewTransition(() => setTheme(mode, true));
    const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    t.ready.then(() => document.documentElement.animate(
      { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
      { duration: 700, easing: "cubic-bezier(.6,0,.2,1)", pseudoElement: "::view-transition-new(root)" }
    )).catch(() => {});
  } else {
    const root = document.documentElement;
    root.classList.add("theming"); setTheme(mode, true);
    setTimeout(() => root.classList.remove("theming"), 600);
  }
});

/* ---------- interactions ---------- */
document.addEventListener("click", e => {
  const cell = e.target.closest("[data-cell]");
  if (cell && canWrite) {
    const [sid, stid] = cell.dataset.cell.split("|");
    const sess = S.sessions.get(sid), cur = sess.att?.[stid] || "u";
    const nx = drop() ? (cur === "p" ? "u" : "p") : STATES[(STATES.indexOf(cur) + 1) % STATES.length];
    cell.className = `cell s-${cellCls(nx)}${sess.notes?.[stid] ? " note" : ""} pop`; cell.textContent = drop() ? (nx === "p" ? "✓" : "") : STATE_MARK[nx];
    write("sessions/" + sid, d => d.update({ att: { [stid]: nx } }));
    return;
  }
  const cp = e.target.closest("[data-copy]");
  if (cp) {
    const v = cp.dataset.copy;
    try { navigator.clipboard.writeText(v).then(() => toast("Zkopírováno: " + v), () => selectText(cp)); } catch { selectText(cp); }
    return;
  }
  const ct = e.target.closest("[data-contact]"); if (ct) return openContact(ct.dataset.contact);
  const fri = e.target.closest("[data-fri]"); if (fri) return openFriday(fri.dataset.fri);
  const sh = e.target.closest("[data-sess]"); if (sh) return openSession(sh.dataset.sess);
  const ep = e.target.closest("[data-edit-project]"); if (ep) return openProject(ep.dataset.editProject);
  const cd = e.target.closest("[data-card]"); if (cd) return openCard(cd.dataset.card);
  const st = e.target.closest("[data-stu]"); if (st) return openStudent(st.dataset.stu);
  if (e.target.closest("[data-go='new-project']")) { location.hash = "projekty"; return openProject(null); }
});
$("#addSession").onclick = () => openSession(null);
$("#addProject").onclick = () => openProject(null);
$("#addStudent").onclick = () => openStudent(null);
$("#addContact").onclick = () => openContact(null);

function selectText(btn) {
  const span = btn.previousElementSibling, r = document.createRange();
  r.selectNodeContents(span); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
  toast("Text je označený, zkopíruj ho Ctrl+C.");
}

/* contact dialog */
let editCon = null;
function openContact(id) {
  if (!canWrite) return;
  editCon = id; const c = id ? S.contacts.get(id) : null;
  $("#conTitle").textContent = c ? c.name : "Nový kontakt";
  $("#cName").value = c?.name || ""; $("#cType").value = c?.type || "teacher"; $("#cRole").value = c?.role || "";
  $("#cPhone").value = c?.phone || ""; $("#cEmail").value = c?.email || ""; $("#cNote").value = c?.note || "";
  $("#cGroup").value = c?.group || "";
  $("#cGroups").innerHTML = [...new Set([...S.contacts.values()].map(x => x.group).filter(Boolean))].map(g => `<option value="${esc(g)}"></option>`).join("");
  syncGroup();
  $("#cDel").hidden = !c;
  armDelete($("#cDel"), () => { write("contacts/" + id, d => d.delete()); $("#dlgContact").close(); toast("Kontakt smazán."); });
  $("#dlgContact").showModal();
}
function syncGroup() {
  const other = $("#cType").value === "other";
  $("#cGroupWrap").hidden = !other; $("#cGroup").required = other;
}
$("#cType").addEventListener("change", () => { syncGroup(); if ($("#cType").value === "other") $("#cGroup").focus(); });
$("#fContact").addEventListener("submit", e => {
  if (e.submitter?.value === "cancel") return;
  const data = { name: $("#cName").value.trim(), type: $("#cType").value, group: $("#cType").value === "other" ? $("#cGroup").value.trim() : "", role: $("#cRole").value.trim(), phone: $("#cPhone").value.trim(), email: $("#cEmail").value.trim(), note: $("#cNote").value.trim() };
  if (editCon) write("contacts/" + editCon, d => d.update(data)).then(() => toast("Kontakt uložen."));
  else { const id = "c-" + Date.now().toString(36); write("contacts/" + id, d => d.set(data)).then(() => toast("Kontakt přidán.")); }
});

function armDelete(btn, fn) {
  btn.classList.remove("armed"); btn.textContent = btn.dataset.label || (btn.dataset.label = btn.textContent);
  btn.onclick = () => {
    if (!btn.classList.contains("armed")) { btn.classList.add("armed"); btn.textContent = "Opravdu smazat?"; return; }
    fn();
  };
}

/* friday dialog */
let editFri = null;
function openFriday(date) {
  const s = S.sessions.get(date);
  if (s) return openSession(date);
  if (!canWrite) return;
  editFri = date; const off = S.cancelled.get(date);
  const regular = isRegular(dow(date));
  $("#friTitle").textContent = cap(dayName(date)) + " " + fmtDate(date, true);
  $("#friInfo").textContent = off ? "Zapsáno jako odpadlé."
    : !regular ? "Tento den není pravidelný termín kroužku. Můžeš sem přidat mimořádnou schůzku."
    : !isOver(date) ? "Budoucí termín. Můžeš ho předem označit jako odpadlý, nebo naplánovat schůzku."
    : "K tomuto termínu zatím není docházka ani důvod, proč odpadl.";
  $("#friReason").value = off?.reason || "";
  const showCancel = regular || !!off;
  $("#friReason").closest("label").hidden = !showCancel; $("#friChips").hidden = !showCancel; $("#friSave").hidden = !showCancel;
  $("#friUndo").hidden = !off;
  $("#friHeld").textContent = !regular && !off ? "Přidat schůzku na tento den" : !isOver(date) ? "Naplánovat schůzku" : "Proběhlo – zapsat docházku";
  $("#dlgFriday").showModal();
}
$("#friChips").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { $("#friReason").value = b.textContent; $("#friReason").focus(); } });
$("#friUndo").onclick = () => { write("cancelled/" + editFri, d => d.delete()).then(() => toast("Termín už není označený jako odpadlý.")); $("#dlgFriday").close(); };
$("#friHeld").onclick = () => {
  const d = editFri; $("#dlgFriday").close();
  if (S.cancelled.has(d)) write("cancelled/" + d, x => x.delete());
  openSession(null, d);
};
$("#fFriday").addEventListener("submit", e => {
  if (e.submitter?.value === "cancel") return;
  const reason = $("#friReason").value.trim();
  write("cancelled/" + editFri, d => d.set({ date: editFri, reason })).then(() => toast("Uloženo: " + fmtDate(editFri, true) + " odpadlo."));
});

/* session dialog */
let editSess = null, sessDraft = null;
function openSession(id, presetDate) {
  if (!canWrite && !id) return;
  editSess = id; const s = id ? S.sessions.get(id) : null;
  sessDraft = { att: { ...(s?.att || {}) }, notes: { ...(s?.notes || {}) } };
  $("#sessTitle").textContent = s ? "Schůzka " + fmtDate(s.date, true) : "Nová schůzka";
  $("#sessDate").value = s?.date || presetDate || today; $("#sessDate").disabled = !!s;
  $("#sessTopic").value = s?.topic || "";
  const dDate = s?.date || presetDate || today;
  $("#sessStart").value = s?.start || tStart(dDate); $("#sessEnd").value = s?.end || tEnd(dDate);
  $("#sessList").innerHTML = students().map(st => {
    const v = sessDraft.att[st.id] || "u";
    return `<div class="sessrow" data-row="${st.id}"><span><b>${esc(st.surname)}</b> ${esc(st.first)} ${clsTag(st)}</span>
      <span class="seg">${(drop() ? ["p", "u"] : ["p", "a", "u", "x"]).map(k => `<button type="button" class="s-${k}" data-set="${k}" aria-pressed="${drop() ? (k === "p") === (v === "p") : v === k}">${lbl(k)}</button>`).join("")}</span>
      <input type="text" id="note-${st.id}" placeholder="Poznámka" value="${esc(sessDraft.notes[st.id] || "")}"></div>`;
  }).join("");
  $("#sessDel").hidden = !s;
  armDelete($("#sessDel"), () => { write("sessions/" + id, d => d.delete()); $("#dlgSession").close(); toast("Schůzka smazána."); });
  $("#fSession").querySelectorAll("input,button[data-set]").forEach(el => el.disabled = !canWrite && el.id !== "sessDate");
  $("#sessSave").hidden = !canWrite; $("#sessQuick").hidden = !canWrite;
  $("#allP").hidden = drop(); $("#allU").textContent = drop() ? "Nikdo" : "Vymazat";
  $("#quickHint").textContent = drop() ? "Klikni na „Přišel“ u těch, kdo dnes dorazili." : "Pak jen odklikni, kdo chybí.";
  $("#dlgSession").showModal();
}
// quick fill: everyone present (except not-yet-enrolled), or clear all
function setAll(v) {
  if (!canWrite) return;
  document.querySelectorAll("#sessList [data-row]").forEach(row => {
    const id = row.dataset.row;
    if (v === "p" && sessDraft.att[id] === "x") return;
    sessDraft.att[id] = v;
    row.querySelectorAll("[data-set]").forEach(x => x.setAttribute("aria-pressed", x.dataset.set === v));
  });
  $("#dlgSession").dataset.dirty = "1";
}
// read a photo of the filled-in paper sheet and pre-fill the marks (the viewer reviews and saves)
$("#sessPhoto").addEventListener("change", async e => {
  const file = e.target.files[0]; e.target.value = "";
  if (!file || !canWrite) return;
  const sample = null;
  const lim = sample ? await sample.limits().catch(() => null) : null;
  if (!sample || !lim?.images) { toast("Čtení fotky tady není dostupné. Otevři přehled na claude.ai."); return; }
  const list = students().map((s, i) => `${i + 1}. id=${s.id}: ${s.surname} ${s.first}`).join("\n");
  const hint = $("#quickHint"), old = hint.textContent;
  hint.textContent = "Čtu fotku… (může to chvíli trvat)"; $("#fromPhoto").classList.add("busy");
  try {
    const res = await sample.json(
      `Na fotce je vyplněný papírový docházkový list kroužku. Tabulka má sloupce: číslo, jméno, „Přítomen“ a „Nepřítomen“ se zaškrtávacími políčky (zaškrtnuto = křížek ☒). Vedle jména může být ručně psaná poznámka.\n\n` +
      `Studenti v přehledu (jména na papíře mohou být v pořadí Jméno Příjmení i Příjmení Jméno):\n${list}\n\n` +
      `Pro každého studenta urči stav: "p" = křížek ve sloupci Přítomen, "a" = křížek ve sloupci Nepřítomen, "u" = nic nezaškrtnuto nebo nečitelné. Ručně psané poznámky přepiš přesně.\n` +
      `Odpověz pouze JSON ve tvaru {"date": "RRRR-MM-DD" nebo null (datum z hlavičky listu), "marks": {"<id>": "p"|"a"|"u"}, "notes": {"<id>": "text"}}. Použij jen id ze seznamu výše.`,
      { images: [file], modelTier: "default", cache: false });
    const valid = new Set(students().map(s => s.id));
    let n = 0;
    Object.entries(res?.marks || {}).forEach(([id, v0]) => {
      let v = v0;
      if (!valid.has(id) || !["p", "a", "u"].includes(v) || sessDraft.att[id] === "x" && v === "u") return;
      if (drop() && v === "a") v = "u";   // SŠ only knows "came" or blank
      sessDraft.att[id] = v; n++;
      document.querySelectorAll(`#sessList [data-row="${id}"] [data-set]`).forEach(x => x.setAttribute("aria-pressed", x.dataset.set === v));
    });
    Object.entries(res?.notes || {}).forEach(([id, txt]) => {
      const inp = $("#note-" + id); if (valid.has(id) && inp && !inp.value && typeof txt === "string") inp.value = txt.slice(0, 200);
    });
    if (!editSess && typeof res?.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(res.date)) $("#sessDate").value = res.date;
    $("#dlgSession").dataset.dirty = "1";
    toast(n ? `Načteno z fotky: ${n} studentů. Zkontroluj a ulož.` : "Na fotce se nepodařilo nic přečíst.");
  } catch (err) {
    toast(err?.code === "not_granted" ? "Bez povolení nejde fotku přečíst." : err?.code === "rate_limited" ? "Moc požadavků najednou, zkus to za chvíli." : err?.code === "image_rejected" ? "Tuhle fotku nejde použít, zkus jinou (JPG nebo PNG)." : "Fotku se nepodařilo přečíst, zkus to znovu.");
  } finally { hint.textContent = old; $("#fromPhoto").classList.remove("busy"); }
});
$("#allP").onclick = () => setAll("p");
$("#allU").onclick = () => setAll("u");
$("#sessList").addEventListener("click", e => {
  const b = e.target.closest("[data-set]"); if (!b) return;
  const row = b.closest("[data-row]");
  sessDraft.att[row.dataset.row] = b.dataset.set;
  $("#dlgSession").dataset.dirty = "1";
  row.querySelectorAll("[data-set]").forEach(x => x.setAttribute("aria-pressed", x === b));
});
$("#fSession").addEventListener("submit", e => {
  if (e.submitter?.value === "cancel") return;
  const date = $("#sessDate").value; if (!date) return;
  const id = editSess || date;
  if (!editSess && S.sessions.has(id)) { e.preventDefault(); toast("Schůzka s tímto datem už existuje."); return; }
  // keep marks and notes of inactive students untouched; only listed students are rewritten
  const notes = { ...sessDraft.notes };
  students().forEach(s => { const v = $("#note-" + s.id).value.trim(); if (v) notes[s.id] = v; else delete notes[s.id]; });
  const att = { ...sessDraft.att }; students().forEach(s => att[s.id] = sessDraft.att[s.id] || "u");
  const start = $("#sessStart").value || tStart(date), end = $("#sessEnd").value || tEnd(date);
  write("sessions/" + id, d => d.set({ date, topic: $("#sessTopic").value.trim(), start, end, att, notes })).then(() => toast("Schůzka uložena."));
});

/* project dialog */
let editProj = null;
function openProject(id) {
  if (!canWrite) return;
  editProj = id; const p = id ? S.projects.get(id) : null;
  $("#projTitle").textContent = p ? "Upravit projekt" : "Nový projekt";
  $("#pName").value = p?.name || ""; $("#pDesc").value = p?.desc || "";
  $("#pStatus").value = p?.status || "idea"; $("#pProg").value = p?.progress || 0; $("#pProgV").textContent = ($("#pProg").value) + " %";
  const mem = new Map((p?.members || []).map(m => [m.id, m.role || ""]));
  $("#pMembers").innerHTML = students().map(s => `<label class="member"><input type="checkbox" id="pm-${s.id}" data-m="${s.id}" ${mem.has(s.id) ? "checked" : ""}><span><b>${esc(s.surname)}</b> ${esc(s.first)}</span><input type="text" id="pr-${s.id}" placeholder="role v projektu" value="${esc(mem.get(s.id) || "")}"></label>`).join("");
  $("#pDel").hidden = !p;
  armDelete($("#pDel"), () => { write("projects/" + id, d => d.delete()); $("#dlgProject").close(); toast("Projekt smazán."); });
  $("#dlgProject").showModal();
}
$("#pProg").oninput = () => $("#pProgV").textContent = $("#pProg").value + " %";
$("#pMembers").addEventListener("input", e => {
  if (e.target.id?.startsWith("pr-") && e.target.value) $("#pm-" + e.target.id.slice(3)).checked = true;
});
$("#fProject").addEventListener("submit", e => {
  if (e.submitter?.value === "cancel") return;
  const members = [...document.querySelectorAll("#pMembers [data-m]:checked")].map(c => ({ id: c.dataset.m, role: $("#pr-" + c.dataset.m).value.trim() }));
  const data = { name: $("#pName").value.trim(), desc: $("#pDesc").value.trim(), status: $("#pStatus").value, progress: +$("#pProg").value, members };
  if (editProj) write("projects/" + editProj, d => d.update(data)).then(() => toast("Projekt uložen."));
  else { const id = "p-" + Date.now().toString(36); write("projects/" + id, d => d.set({ ...data, log: [], created: today, year: SY })).then(() => toast("Projekt přidán.")); }
});

/* student card: everything about one student in one place */
const initials = s => ((s.first || "")[0] || "") + ((s.surname || "")[0] || "");
const photoBox = (el, s, id) => { el.innerHTML = isAsset(id) ? `<img src="${id}" alt="Fotka: ${esc(s.first)} ${esc(s.surname)}">` : esc(initials(s).toUpperCase()); };
let cardStu = null;
function openCard(id) {
  const s = S.students.get(id); if (!s) return;
  cardStu = id;
  const r = stats(id), f = S.family.get(id) || {};
  photoBox($("#cardPhoto"), s, f.photo);
  $("#cardName").innerHTML = `${esc(s.surname)} <span style="font-weight:500">${esc(s.first)}</span>`;
  $("#cardMeta").innerHTML = [s.nick ? `„${esc(s.nick)}“` : "", drop() && s.cls ? esc(s.cls) : "", s.role ? esc(s.role) : "", s.inactive ? "neaktivní" : "", !drop() && s.toSchool ? `→ ${esc(s.toSchool)}` : "", GROUP[G].short].filter(Boolean).join(" · ");
  const offs = fridays().filter(x => x.state === "off").length;
  $("#cardStats").innerHTML = drop()
    ? `<div><b>${r.p}×</b><span>na kroužku</span></div><div><b>${r.last ? fmtDate(r.last) : "—"}</b><span>naposledy</span></div><div><b>${esc(s.cls || "—")}</b><span>${s.teacher ? "třídní: " + esc(s.teacher) : "třída"}</span></div>`
    : `<div><b>${r.pct == null ? "—" : r.pct + " %"}</b><span>účast</span></div><div><b>${r.p} / ${r.n}</b><span>přítomen / schůzek</span></div><div><b>${offs}</b><span>odpadlých termínů</span></div>`;
  const att = past().slice().reverse().map(x => { const v = x.att?.[id] || "u", note = x.notes?.[id]; return `<div><time>${fmtDate(x.date, true)}</time><span class="pill s-${cellCls(v)}">${lbl(v)}</span><em>${esc(note || x.topic || "")}</em></div>`; }).join("");
  $("#cardAtt").innerHTML = att || `<p class="hint">Zatím žádná proběhlá schůzka.</p>`;
  const projs = projects().filter(p => (p.members || []).some(m => m.id === id));
  $("#cardProj").innerHTML = projs.length ? `<div class="card-proj">${projs.map(p => {
    const role = p.members.find(m => m.id === id)?.role, photos = (p.log || []).filter(l => isAsset(l.photo)).slice(-6);
    return `<article><div class="row"><b>${esc(p.name)}</b><span class="pill st-${p.status}">${STATUS[p.status] || ""}</span><span class="num" style="margin-left:auto">${p.progress || 0} %</span></div>
      ${role ? `<span class="hint">Role: ${esc(role)}</span>` : ""}
      ${photos.length ? `<div class="thumbs">${photos.map(l => `<a href="${l.photo}" target="_blank" rel="noopener"><img src="${l.photo}" alt="" loading="lazy"></a>`).join("")}</div>` : ""}</article>`;
  }).join("")}</div>` : `<p class="hint">Zatím není v žádném projektu.</p>`;
  $("#cardNote").textContent = s.note || ""; $("#cardNote").hidden = !s.note;
  $("#cardEdit").hidden = !canWrite; $("#cardContact").hidden = !canWrite; $("#cardPdf").hidden = drop();
  showCardContacts(false);
  $("#dlgCard").showModal();
}
// the same card window switches between the student's overview and their contacts
function showCardContacts(on) {
  $("#cardMain").hidden = on; $("#cardContacts").hidden = !on;
  $("#cardContact").textContent = on ? "Karta" : "Kontakty";
  if (!on) return;
  const s = S.students.get(cardStu) || {}, f = S.family.get(cardStu) || {};
  const line = (icon, v, label) => v ? `<div class="line">${icon}<span>${esc(v)}</span><button class="copy" type="button" data-copy="${esc(v)}" aria-label="Kopírovat ${label}" title="Kopírovat">${ICON_COPY}</button></div>` : "";
  const block = (title, p) => {
    const body = (p?.name ? `<div class="pname">${esc(p.name)}</div>` : "") + line(ICON_PHONE, p?.phone, "telefon") + line(ICON_MAIL, p?.email, "e-mail");
    return `<div class="who"><span>${title}</span>${body || `<div class="hint">Nevyplněno</div>`}</div>`;
  };
  $("#cardContacts").innerHTML = drop()
    ? `<div class="who"><span>Třídní učitel</span>${s.teacher ? `<div class="pname">${esc(s.teacher)}</div>` : `<div class="hint">Nevyplněno</div>`}</div>${block("Student", f.contact)}`
    : migrBlock(s) + block("Žák", f.contact) + block("Rodič 1", f.parent1) + block("Rodič 2", f.parent2);
}
$("#cardEdit").onclick = () => { const id = cardStu; $("#dlgCard").close(); openStudent(id); };
$("#cardContact").onclick = () => showCardContacts($("#cardContacts").hidden);
$("#cardPdf").onclick = () => cardStu && parentPdf(cardStu);

/* student dialog */
let editStu = null, stuPhoto = null;
$("#sPhoto").addEventListener("change", async e => {
  const file = e.target.files[0]; e.target.value = ""; if (!file) return;
  toast("Nahrávám fotku…");
  try {
    stuPhoto = (await uploadPhoto(await shrinkPhoto(file, 600))).url;
    photoBox($("#sPhotoPrev"), { first: $("#sFirst").value, surname: $("#sSur").value }, stuPhoto);
    $("#sPhotoDel").hidden = false; $("#dlgStudent").dataset.dirty = "1"; toast("Fotka nahrána, nezapomeň uložit.");
  } catch { toast("Fotku se nepodařilo nahrát."); }
});
$("#sPhotoDel").onclick = () => { stuPhoto = null; photoBox($("#sPhotoPrev"), { first: $("#sFirst").value, surname: $("#sSur").value }, null); $("#sPhotoDel").hidden = true; $("#dlgStudent").dataset.dirty = "1"; };
function openStudent(id) {
  if (!canWrite) return;
  editStu = id; const s = id ? S.students.get(id) : null;
  $("#stuTitle").textContent = s ? `${s.surname} ${s.first}` : "Nový student";
  $("#sSur").value = s?.surname || ""; $("#sFirst").value = s?.first || ""; $("#sNick").value = s?.nick || ""; $("#sRole").value = s?.role || ""; $("#sNote").value = s?.note || "";
  $("#sInactive").checked = !!s?.inactive;
  $("#sSchool").hidden = !drop(); $("#fStudent").querySelectorAll("[data-parent]").forEach(f => f.hidden = drop());
  $("#sCls").value = s?.cls || ""; $("#sTeacher").value = s?.teacher || "";
  $("#sMigr").hidden = drop();
  $("#sToSchool").value = s?.toSchool || ""; $("#sToField").value = s?.toField || ""; $("#sToYear").value = s?.toYear || "";
  const all = allStudents();
  $("#toSchoolList").innerHTML = [...new Set(all.map(x => x.toSchool).filter(Boolean))].sort(coll.compare).map(c => `<option value="${esc(c)}"></option>`).join("");
  $("#clsList").innerHTML = [...new Set(all.map(x => x.cls).filter(Boolean))].sort(byCls).map(c => `<option value="${esc(c)}"></option>`).join("");
  $("#teachList").innerHTML = [...new Set(all.map(x => x.teacher).filter(Boolean))].sort(coll.compare).map(c => `<option value="${esc(c)}"></option>`).join("");
  const f = (id && S.family.get(id)) || {};
  stuPhoto = isAsset(f.photo) ? f.photo : null;
  photoBox($("#sPhotoPrev"), s || { first: "", surname: "" }, stuPhoto); $("#sPhotoDel").hidden = !stuPhoto;
  $("#sPhone").value = f.contact?.phone || ""; $("#sEmail").value = f.contact?.email || "";
  ["1", "2"].forEach(n => { const p = f["parent" + n]; $(`#p${n}Name`).value = p?.name || ""; $(`#p${n}Phone`).value = p?.phone || ""; $(`#p${n}Email`).value = p?.email || ""; });
  $("#sDel").hidden = !s; $("#sPdf").hidden = !s || drop();
  armDelete($("#sDel"), () => { write("students/" + id, d => d.delete()); write("family/" + id, d => d.delete()); $("#dlgStudent").close(); toast("Student smazán."); });
  $("#dlgStudent").showModal();
}
// typing a known class fills in its class teacher
$("#sCls").addEventListener("change", () => {
  if ($("#sTeacher").value.trim()) return;
  const c = $("#sCls").value.trim().toLowerCase(), t = allStudents().find(x => x.cls?.toLowerCase() === c && x.teacher)?.teacher;
  if (t) $("#sTeacher").value = t;
});
$("#fStudent").addEventListener("submit", e => {
  if (e.submitter?.value === "cancel") return;
  const v = id => $(id).value.trim();
  const fam = {
    contact: { phone: v("#sPhone"), email: v("#sEmail") },
    parent1: { name: v("#p1Name"), phone: v("#p1Phone"), email: v("#p1Email") },
    parent2: { name: v("#p2Name"), phone: v("#p2Phone"), email: v("#p2Email") },
    photo: stuPhoto || null };
  const data = { surname: v("#sSur"), first: v("#sFirst"), nick: v("#sNick"), role: v("#sRole"), note: v("#sNote"), inactive: $("#sInactive").checked };
  if (!drop()) { data.toSchool = v("#sToSchool"); data.toField = v("#sToField"); data.toYear = v("#sToYear"); }
  if (drop()) { data.cls = v("#sCls"); data.teacher = v("#sTeacher"); const old = (editStu && S.family.get(editStu)) || {}; if (old.parent1) fam.parent1 = old.parent1; if (old.parent2) fam.parent2 = old.parent2; if (!old.parent1 && !old.parent2) { delete fam.parent1; delete fam.parent2; } }
  let id = editStu;
  if (!id) { id = slug(data.surname); while (S.students.has(id)) id += "-" + Math.random().toString(36).slice(2, 5); }
  write("students/" + id, d => editStu ? d.update(data) : d.set(data)).then(() => toast("Uloženo."));
  write("family/" + id, d => d.set(fam));
});

/* ---------- PDF export ---------- */
// Pages are drawn on an A4 canvas (200 dpi) with the page's own fonts, so Czech letters render exactly, then wrapped into a PDF.
const PW = 1654, PH = 2339, PM = 130;
const INK = "#1c1d20", GREY = "#6a6c72", LINE = "#d9d9dd", RED = "#ac1f29", CHAR = "#33353a";
const ST_PRINT = { p: ["Přítomen", "#1f8a57"], a: ["Nepřítomen", "#c62f3f"], u: ["Nezapsáno", "#b07a0c"], x: ["Ještě nenastoupil", "#7d7f86"] };
const asciiName = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9.]+/g, "_");
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

function pdfHeader(ctx, title, subtitle, W = PW, H = PH) {
  const logo = $("#logoPng");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, H);
  if (logo?.complete) ctx.drawImage(logo, PM, PM - 10, 120, 120);
  ctx.fillStyle = INK; ctx.font = '800 72px "Bricolage Grotesque", sans-serif'; ctx.textBaseline = "alphabetic";
  ctx.fillText(title, PM + 150, PM + 62);
  ctx.fillStyle = GREY; ctx.font = '500 30px "Inter", sans-serif';
  ctx.fillText(subtitle, PM + 152, PM + 106);
  const g = ctx.createLinearGradient(PM, 0, W - PM, 0); g.addColorStop(0, RED); g.addColorStop(1, CHAR);
  ctx.fillStyle = g; ctx.fillRect(PM, PM + 140, W - 2 * PM, 6);
  return PM + 210;
}
function pdfFooter(ctx, page, pages, W = PW, H = PH) {
  ctx.fillStyle = GREY; ctx.font = '400 24px "Inter", sans-serif';
  ctx.textAlign = "left"; ctx.fillText("Kroužek DuklaLabs · vygenerováno " + fmtDate(today, true), PM, H - 90);
  ctx.textAlign = "right"; ctx.fillText(`Strana ${page} / ${pages}`, W - PM, H - 90);
  ctx.textAlign = "left";
}
function pdfBox(ctx, cx, cy, checked) {
  const s = 40; ctx.lineWidth = 3; ctx.strokeStyle = CHAR;
  ctx.strokeRect(cx - s / 2, cy - s / 2, s, s);
  if (checked) { ctx.beginPath(); ctx.moveTo(cx - 13, cy - 13); ctx.lineTo(cx + 13, cy + 13); ctx.moveTo(cx + 13, cy - 13); ctx.lineTo(cx - 13, cy + 13); ctx.lineWidth = 4; ctx.stroke(); }
}
function pdfName(ctx, s, x, y) {
  ctx.fillStyle = INK; ctx.font = '700 34px "Inter", sans-serif'; ctx.fillText(s.surname, x, y);
  const w = ctx.measureText(s.surname + " ").width;
  ctx.font = '400 29px "Inter", sans-serif'; ctx.fillText(s.first, x + w, y);
}
function fitText(ctx, t, maxW) {
  if (ctx.measureText(t).width <= maxW) return t;
  while (t.length > 1 && ctx.measureText(t + "…").width > maxW) t = t.slice(0, -1);
  return t + "…";
}
// cols: [{label, w, align}], rows: [(ctx, cellX[], y, h) => void]; returns pages of row chunks
function pdfTable(ctx, y, cols, rows, rowH) {
  const xs = []; let x = PM; cols.forEach(c => { xs.push(x); x += c.w; });
  ctx.fillStyle = "#eeeef1"; ctx.fillRect(PM, y, PW - 2 * PM, 70);
  ctx.fillStyle = INK; ctx.font = '700 26px "Inter", sans-serif';
  cols.forEach((c, i) => { ctx.textAlign = c.align || "left"; ctx.fillText(c.label, c.align === "center" ? xs[i] + c.w / 2 : xs[i] + 18, y + 45); });
  ctx.textAlign = "left"; y += 70;
  rows.forEach((draw, i) => {
    if (i % 2) { ctx.fillStyle = "#f8f8f9"; ctx.fillRect(PM, y, PW - 2 * PM, rowH); }
    draw(ctx, xs, y, rowH);
    ctx.fillStyle = LINE; ctx.fillRect(PM, y + rowH - 2, PW - 2 * PM, 2);
    y += rowH;
  });
  ctx.strokeStyle = LINE; ctx.lineWidth = 2; ctx.strokeRect(PM, y - rows.length * rowH - 70, PW - 2 * PM, rows.length * rowH + 70);
  return y;
}
function chunk(arr, first, rest) {
  const out = [arr.slice(0, first)];
  for (let i = first; i < arr.length; i += rest) out.push(arr.slice(i, i + rest));
  return out;
}
const pdfSub = () => `Kroužek DuklaLabs · ${GROUP[G].name} · školní rok ${yearLabel()}`;
async function savePdf(filename, drawPages, landscape = false) {
  if (G !== "zs") filename = filename.replace(/^Dochazka_/, "Dochazka_SS_");
  const W = landscape ? PH : PW, H = landscape ? PW : PH;
  if (!window.jspdf) { toast("Knihovna pro PDF se nenačetla, obnov stránku."); return; }
  await Promise.all(['800 72px "Bricolage Grotesque"', '700 34px "Inter"', '400 29px "Inter"'].map(f => document.fonts.load(f).catch(() => {})));
  const pdf = new window.jspdf.jsPDF({ unit: "mm", format: "a4", orientation: landscape ? "landscape" : "portrait", compress: true });
  drawPages.forEach((draw, i) => {
    const c = document.createElement("canvas"); c.width = W; c.height = H;
    const ctx = c.getContext("2d"); draw(ctx); pdfFooter(ctx, i + 1, drawPages.length, W, H);
    if (i) pdf.addPage();
    pdf.addImage(c.toDataURL("image/png"), "PNG", 0, 0, landscape ? 297 : 210, landscape ? 210 : 297, undefined, "FAST");
  });
  try {
    downloadBlob(new Blob([pdf.output("arraybuffer")], { type: "application/pdf" }), filename);
    toast("PDF uloženo: " + filename);
  } catch {
    toast("PDF se nepodařilo uložit.");
  }
}

/* daily sheet: all students for one date */
function dailyPdf(date, topic, att, notes, time) {
  return savePdf(`Dochazka_${fmtDate(date, true).replace(/ /g, "")}.pdf`, dailyPages(date, topic, att, notes, time));
}
function dailyPages(date, topic, att, notes, time = sessTime(null, date)) {
  const st = students(), per = 20, dr = drop();
  const cols = dr ? [{ label: "Č.", w: 90, align: "center" }, { label: "Jméno", w: 590 }, { label: "Třída", w: 200, align: "center" }, { label: "Přišel", w: 200, align: "center" }, { label: "Poznámka", w: PW - 2 * PM - 1080 }]
    : [{ label: "Č.", w: 90, align: "center" }, { label: "Jméno", w: 590 }, { label: "Přítomen", w: 200, align: "center" }, { label: "Nepřítomen", w: 200, align: "center" }, { label: "Poznámka", w: PW - 2 * PM - 1080 }];
  const rows = st.map((s, i) => (ctx, xs, y, h) => {
    const v = att[s.id] || "u", mid = y + h / 2;
    ctx.fillStyle = GREY; ctx.font = '500 28px "Inter", sans-serif'; ctx.textAlign = "center"; ctx.fillText(String(i + 1), xs[0] + 45, mid + 10); ctx.textAlign = "left";
    pdfName(ctx, s, xs[1] + 18, mid + 12);
    if (dr) { ctx.fillStyle = INK; ctx.font = '500 28px "Inter", sans-serif'; ctx.textAlign = "center"; ctx.fillText(s.cls || "", xs[2] + 100, mid + 10); ctx.textAlign = "left"; pdfBox(ctx, xs[3] + 100, mid, v === "p"); }
    else { pdfBox(ctx, xs[2] + 100, mid, v === "p"); pdfBox(ctx, xs[3] + 100, mid, v === "a"); }
    const note = notes[s.id] || (!dr && v === "x" ? "Ještě nenastoupil" : "");
    if (note) { ctx.fillStyle = GREY; ctx.font = 'italic 400 24px "Inter", sans-serif'; ctx.fillText(fitText(ctx, note, cols[4].w - 30), xs[4] + 16, mid + 9); }
  });
  const present = st.filter(s => att[s.id] === "p").length, counted = st.filter(s => (att[s.id] || "u") !== "x").length;
  const pages = chunk(rows, per, per + 4).map((part, pi, all) => ctx => {
    let y = pdfHeader(ctx, "Docházka", pdfSub());
    if (pi === 0) {
      ctx.fillStyle = INK; ctx.font = '700 36px "Inter", sans-serif'; ctx.fillText("Datum:", PM, y);
      ctx.font = '400 36px "Inter", sans-serif'; ctx.fillText(`${fmtDate(date, true)}   ·   ${time}`, PM + ctx.measureText("Datum: ").width + 18, y);
      if (topic) { ctx.fillStyle = GREY; ctx.font = '400 28px "Inter", sans-serif'; ctx.fillText("Téma: " + topic, PM, y + 48); y += 48; }
      y += 50;
    }
    y = pdfTable(ctx, y, cols, part, 82);
    if (pi === all.length - 1) {
      ctx.fillStyle = INK; ctx.font = '600 30px "Inter", sans-serif';
      ctx.fillText(dr ? `Přišlo ${present} studentů` : `Přítomno ${present} z ${counted} studentů`, PM, y + 70);
    }
  });
  return pages;
}

/* summary: students × Fridays on landscape pages (at most 18 Fridays per page) */
function summaryPdf() {
  const LW = PH, LH = PW;
  const days = fridays().filter(f => f.state === "held" || f.state === "off");
  if (!days.length) return toast("Zatím není co exportovat.");
  // landscape A4 is only 1654 px tall: fit header, table, totals, legend and footer on one page
  const st = students(), perPage = 18, nameW = 470, pctW = 150, dr = drop();
  const rowH = Math.max(36, Math.min(70, Math.floor((LH - 340 - 96 - 64 - 160 - 150) / Math.max(st.length, 1))));
  const parts = chunk(days, perPage, perPage);
  const pages = parts.map((part, pi) => ctx => {
    let y = pdfHeader(ctx, "Souhrn docházky", `${pdfSub()} · ${fmtDate(days[0].date, true)} – ${fmtDate(days[days.length - 1].date, true)}`, LW, LH);
    const colW = Math.min(90, (LW - 2 * PM - nameW - pctW) / part.length);
    const tableW = nameW + colW * part.length + pctW;
    // header row
    ctx.fillStyle = "#eeeef1"; ctx.fillRect(PM, y, tableW, 96);
    ctx.fillStyle = INK; ctx.font = '700 26px "Inter", sans-serif'; ctx.fillText("Student", PM + 18, y + 58);
    part.forEach((f, i) => {
      const cx = PM + nameW + i * colW + colW / 2;
      ctx.textAlign = "center"; ctx.fillStyle = f.state === "off" ? GREY : INK;
      ctx.font = '700 24px "Inter", sans-serif'; ctx.fillText(fmtDate(f.date), cx, y + 46);
      ctx.font = '400 19px "Inter", sans-serif'; ctx.fillStyle = GREY; ctx.fillText(f.state === "off" ? "odpadlo" : DAY_SHORT[new Date(f.date + "T12:00").getDay()], cx, y + 74);
    });
    ctx.fillStyle = INK; ctx.font = '700 26px "Inter", sans-serif'; ctx.textAlign = "center"; ctx.fillText(dr ? "Přišel" : "Účast", PM + nameW + colW * part.length + pctW / 2, y + 58);
    ctx.textAlign = "left"; y += 96;
    const top = y;
    st.forEach((s, ri) => {
      if (ri % 2) { ctx.fillStyle = "#f8f8f9"; ctx.fillRect(PM, y, tableW, rowH); }
      pdfName(ctx, s, PM + 18, y + rowH / 2 + 12);
      if (dr && s.cls) { ctx.fillStyle = GREY; ctx.font = '500 22px "Inter", sans-serif'; ctx.textAlign = "right"; ctx.fillText(s.cls, PM + nameW - 16, y + rowH / 2 + 9); ctx.textAlign = "left"; }
      part.forEach((f, i) => {
        const cx = PM + nameW + i * colW + colW / 2, cy = y + rowH / 2;
        if (f.state === "off") { ctx.fillStyle = "#ececef"; ctx.fillRect(cx - colW / 2, y, colW, rowH); return; }
        const v = f.sess.att?.[s.id] || "u";
        if (dr && v !== "p") return;
        const [, col] = ST_PRINT[v], sz = Math.min(44, colW - 18, rowH - 14);
        ctx.beginPath(); ctx.roundRect(cx - sz / 2, cy - sz / 2, sz, sz, 9);
        if (v === "p" || v === "a") { ctx.fillStyle = col; ctx.fill(); ctx.fillStyle = "#fff"; }
        else { ctx.lineWidth = 3; ctx.strokeStyle = col; ctx.stroke(); ctx.fillStyle = col; }
        ctx.font = '700 26px "Inter", sans-serif'; ctx.textAlign = "center";
        ctx.fillText(v === "p" ? "✓" : v === "a" ? "✕" : v === "x" ? "–" : "", cx, cy + 9); ctx.textAlign = "left";
      });
      const r = stats(s.id);
      ctx.textAlign = "center"; ctx.font = '700 28px "Inter", sans-serif';
      ctx.fillStyle = dr ? (r.p ? "#1f8a57" : GREY) : r.pct == null ? GREY : r.pct >= 75 ? "#1f8a57" : r.pct >= 50 ? "#b07a0c" : "#c62f3f";
      ctx.fillText(dr ? r.p + "×" : r.pct == null ? "—" : r.pct + " %", PM + nameW + colW * part.length + pctW / 2, y + rowH / 2 + 10); ctx.textAlign = "left";
      ctx.fillStyle = LINE; ctx.fillRect(PM, y + rowH - 2, tableW, 2);
      y += rowH;
    });
    // totals row
    ctx.fillStyle = "#eeeef1"; ctx.fillRect(PM, y, tableW, 64);
    ctx.fillStyle = INK; ctx.font = '600 24px "Inter", sans-serif'; ctx.fillText("Přítomno celkem", PM + 18, y + 41);
    part.forEach((f, i) => {
      if (f.state === "off") return;
      ctx.textAlign = "center"; ctx.fillText(String(Object.values(f.sess.att || {}).filter(v => v === "p").length), PM + nameW + i * colW + colW / 2, y + 41);
    });
    ctx.textAlign = "left";
    ctx.strokeStyle = LINE; ctx.lineWidth = 2; ctx.strokeRect(PM, top - 96, tableW, y + 64 - (top - 96));
    // legend + cancelled reasons on the last page
    y += 110;
    const legend = dr ? [["p", "Přišel"]] : [["p", "Přítomen"], ["a", "Nepřítomen"], ["u", "Nezapsáno"], ["x", "Ještě nenastoupil"]];
    let lx = PM; ctx.font = '500 24px "Inter", sans-serif';
    legend.forEach(([k, label]) => {
      const col = ST_PRINT[k][1]; ctx.beginPath(); ctx.roundRect(lx, y - 26, 32, 32, 7);
      if (k === "p" || k === "a") { ctx.fillStyle = col; ctx.fill(); } else { ctx.lineWidth = 3; ctx.strokeStyle = col; ctx.stroke(); }
      ctx.fillStyle = INK; ctx.fillText(label, lx + 44, y - 1); lx += 74 + ctx.measureText(label).width;
    });
    ctx.fillStyle = "#ececef"; ctx.fillRect(lx, y - 26, 32, 32); ctx.fillStyle = INK; ctx.fillText("Kroužek odpadl", lx + 44, y - 1);
    if (pi === parts.length - 1) {
      const offs = days.filter(f => f.state === "off");
      if (offs.length) {
        ctx.fillStyle = GREY; ctx.font = '400 23px "Inter", sans-serif';
        ctx.fillText(fitText(ctx, "Odpadlo: " + offs.map(f => fmtDate(f.date) + (f.off.reason ? " (" + f.off.reason + ")" : "")).join(", "), LW - 2 * PM), PM, y + 50);
      }
    }
  });
  return savePdf("Dochazka_souhrn.pdf", pages, true);
}

/* every held Friday, one sheet per page */
function allDaysPdf() {
  const held = past();
  if (!held.length) return toast("Zatím neproběhla žádná schůzka.");
  const pages = held.flatMap(s => dailyPages(s.date, s.topic || "", { ...(s.att || {}) }, { ...(s.notes || {}) }, sessTime(s)));
  return savePdf("Dochazka_vsechny_patky.pdf", pages);
}

$("#exportPdf").onclick = () => {
  const ss = sessions();
  $("#xDay").innerHTML = ss.slice().reverse().map(s => `<option value="${s.id}">${fmtDate(s.date, true)}${!isOver(s.date, s) ? " (plán)" : ""}</option>`).join("");
  $("#xParentOpt").hidden = drop();
  if (drop() && document.querySelector("input[name=xkind][value=parent]").checked) document.querySelector("input[name=xkind][value=summary]").checked = true;
  $("#xStu").innerHTML = allStudents().map(s => `<option value="${s.id}">${esc(s.surname)} ${esc(s.first)}</option>`).join("");
  $("#dlgExport").showModal();
};
["#xDay", "#xStu"].forEach((sel, i) => $(sel).addEventListener("focus", () => { document.querySelector(`input[name=xkind][value=${i ? "parent" : "day"}]`).checked = true; }));
$("#fExport").addEventListener("submit", e => {
  if (e.submitter?.value === "cancel") return;
  const kind = document.querySelector("input[name=xkind]:checked").value;
  if (kind === "summary") summaryPdf();
  else if (kind === "alldays") allDaysPdf();
  else if (kind === "parent") parentPdf($("#xStu").value);
  else { const s = S.sessions.get($("#xDay").value); if (s) dailyPdf(s.date, s.topic || "", { ...(s.att || {}) }, { ...(s.notes || {}) }, sessTime(s)); }
});

/* parent report: one student across the year */
function parentPdf(id) {
  const s = S.students.get(id); if (!s) return;
  const r = stats(id);
  const entries = fridays().filter(f => f.state === "held" || f.state === "off").map(f => {
    if (f.state === "off") return { date: f.date, label: "Kroužek odpadl", color: "#7d7f86", note: f.off.reason || "" };
    const v = f.sess.att?.[id] || "u";
    return { date: f.date, label: ST_PRINT[v][0], color: ST_PRINT[v][1], note: f.sess.notes?.[id] || "" };
  });
  const offCount = entries.filter(e => e.label === "Kroužek odpadl").length;
  const cols = [{ label: "Datum", w: 300 }, { label: "Docházka", w: 420 }, { label: "Poznámka", w: PW - 2 * PM - 720 }];
  const rows = entries.map(e => (ctx, xs, y, h) => {
    const mid = y + h / 2;
    ctx.fillStyle = INK; ctx.font = '500 30px "Inter", sans-serif'; ctx.fillText(fmtDate(e.date, true), xs[0] + 18, mid + 10);
    ctx.fillStyle = e.color; ctx.beginPath(); ctx.arc(xs[1] + 32, mid, 11, 0, Math.PI * 2); ctx.fill();
    ctx.font = '600 30px "Inter", sans-serif'; ctx.fillText(e.label, xs[1] + 56, mid + 10);
    if (e.note) { ctx.fillStyle = GREY; ctx.font = 'italic 400 26px "Inter", sans-serif'; ctx.fillText(fitText(ctx, e.note, cols[2].w - 36), xs[2] + 18, mid + 9); }
  });
  const pages = chunk(rows.length ? rows : [], 18, 24).map((part, pi) => ctx => {
    let y = pdfHeader(ctx, "Přehled docházky", pdfSub());
    if (pi === 0) {
      ctx.fillStyle = INK; ctx.font = '800 60px "Bricolage Grotesque", sans-serif'; ctx.fillText(s.surname, PM, y + 10);
      const w = ctx.measureText(s.surname + " ").width;
      ctx.font = '500 48px "Inter", sans-serif'; ctx.fillText(s.first, PM + w, y + 10);
      y += 70;
      const tiles = [["Účast", r.pct == null ? "—" : r.pct + " %"], ["Přítomen", `${r.p} z ${r.n} schůzek`], ["Odpadlé termíny", String(offCount)]];
      const tw = (PW - 2 * PM - 40) / 3;
      tiles.forEach(([k, v], i) => {
        const x = PM + i * (tw + 20);
        ctx.fillStyle = i === 0 ? "#f7e0e2" : "#f1f1f3"; ctx.beginPath(); ctx.roundRect(x, y, tw, 150, 22); ctx.fill();
        ctx.fillStyle = GREY; ctx.font = '600 24px "Inter", sans-serif'; ctx.fillText(k.toUpperCase(), x + 28, y + 48);
        ctx.fillStyle = i === 0 ? RED : INK; ctx.font = '700 48px "Bricolage Grotesque", sans-serif'; ctx.fillText(v, x + 28, y + 112);
      });
      y += 200;
      if (!part.length) { ctx.fillStyle = GREY; ctx.font = '400 30px "Inter", sans-serif'; ctx.fillText("Zatím neproběhla žádná schůzka.", PM, y + 40); return; }
    }
    pdfTable(ctx, y, cols, part, 76);
  });
  return savePdf(`Dochazka_${asciiName(s.surname + "_" + s.first)}.pdf`, pages);
}

$("#sessPdf").onclick = () => {
  const date = $("#sessDate").value; if (!date) return toast("Nejdřív vyber datum.");
  const notes = {}; students().forEach(s => { const v = $("#note-" + s.id)?.value.trim(); if (v) notes[s.id] = v; });
  dailyPdf(date, $("#sessTopic").value.trim(), { ...sessDraft.att }, notes, `${$("#sessStart").value || tStart(date)}–${$("#sessEnd").value || tEnd(date)}`);
};
$("#sPdf").onclick = () => editStu && parentPdf(editStu);
$("#parentPdf").onclick = () => {
  $("#parStu").innerHTML = allStudents().map(s => `<option value="${s.id}">${esc(s.surname)} ${esc(s.first)}</option>`).join("");
  $("#dlgParent").showModal();
};
$("#fParent").addEventListener("submit", e => { if (e.submitter?.value !== "cancel") parentPdf($("#parStu").value); });

/* ---------- shared helpers for saving files and uploading photos ---------- */
async function saveFile(filename, data) {
  try {
    const type = filename.endsWith(".json") ? "application/json"
      : filename.endsWith(".xlsx") ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      : "application/octet-stream";
    const blob = data instanceof Blob ? data : new Blob([data], { type });
    downloadBlob(blob, filename);
    toast("Uloženo: " + filename);
  } catch { toast("Soubor se nepodařilo uložit."); }
}
async function uploadPhoto(blob) {
  const fd = new FormData();
  fd.append("file", blob, "photo.jpg");
  const res = await fetch(BASE + "/api/club/upload", { method: "POST", credentials: "include", body: fd });
  if (!res.ok) { const e = new Error("upload failed"); e.code = res.status === 403 ? "invalid_argument" : "upload_failed"; throw e; }
  return await res.json();
}
// phone photos are large: scale to at most 1600 px and re-encode as JPEG before upload
async function shrinkPhoto(file, max = 1600) {
  try {
    const bmp = await createImageBitmap(file);
    const s = Math.min(1, max / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas"); c.width = Math.round(bmp.width * s); c.height = Math.round(bmp.height * s);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    return await new Promise(r => c.toBlob(r, "image/jpeg", .85));
  } catch { return file; }
}
function loadScript(src) {
  return new Promise((res, rej) => { const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = rej; document.head.append(s); });
}

/* project progress entry, optionally with a photo */
document.addEventListener("change", e => {
  const inp = e.target.closest(".cam input"); if (inp) inp.parentElement.classList.toggle("has", !!inp.files.length);
});
document.addEventListener("submit", async e => {
  const f = e.target.closest("[data-log]"); if (!f) return;
  e.preventDefault();
  const id = f.dataset.log, inp = f.querySelector("input[type=text]"), file = f.querySelector("input[type=file]")?.files[0];
  const text = inp.value.trim();
  if (!text && !file) { toast("Napiš, co se udělalo, nebo přidej fotku."); return; }
  const entry = { date: today, text };
  if (file) {
    toast("Nahrávám fotku…");
    try { entry.photo = (await uploadPhoto(await shrinkPhoto(file))).url; }
    catch { toast("Fotku se nepodařilo nahrát."); return; }
  }
  const p = S.projects.get(id), log = [...(p.log || []), entry];
  f.reset(); f.querySelector(".cam")?.classList.remove("has");
  write("projects/" + id, d => d.update({ log })).then(() => toast("Záznam přidán."));
});

/* state holidays for any school year (Easter computed), school holidays known for 2026/2027 */
function easterSunday(Y) {
  const a = Y % 19, b = Math.floor(Y / 100), c = Y % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31), day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(Y, month - 1, day, 12);
}
const SCHOOL_HOLIDAYS = {
  2026: [["2026-10-29", "2026-10-30", "Podzimní prázdniny"], ["2026-12-23", "2027-01-03", "Vánoční prázdniny"], ["2027-01-29", "2027-01-29", "Pololetní prázdniny"], ["2027-03-25", "2027-03-25", "Velikonoční prázdniny"]],
};
function holidaysFor(y) {
  const one = (m, d, yy, r) => { const k = iso(new Date(yy, m - 1, d)); return [k, k, r]; };
  const es = easterSunday(y + 1), fri = new Date(es), mon = new Date(es); fri.setDate(es.getDate() - 2); mon.setDate(es.getDate() + 1);
  return [
    one(9, 28, y, "Státní svátek"), one(10, 28, y, "Státní svátek"), one(11, 17, y, "Státní svátek"),
    one(12, 24, y, "Štědrý den"), one(12, 25, y, "Vánoce"), one(12, 26, y, "Vánoce"), one(1, 1, y + 1, "Nový rok"),
    [iso(fri), iso(fri), "Velký pátek"], [iso(mon), iso(mon), "Velikonoční pondělí"],
    one(5, 1, y + 1, "Svátek práce"), one(5, 8, y + 1, "Den vítězství"),
    ...(SCHOOL_HOLIDAYS[y] || []),
  ];
}
function holidayRows() {
  const ranges = holidaysFor(SY);
  const sp = $("#holSpring").value;
  if (sp) { const e = new Date(sp + "T12:00"); e.setDate(e.getDate() + 4); ranges.push([sp, iso(e), "Jarní prázdniny"]); }
  const rows = [];
  ranges.forEach(([from, to, reason]) => {
    for (const d = new Date(from + "T12:00"); iso(d) <= to; d.setDate(d.getDate() + 1)) {
      const k = iso(d);
      if (isRegular(d.getDay())) rows.push({ date: k, reason, done: S.sessions.has(k) || S.cancelled.has(k) });
    }
  });
  return rows.sort((a, b) => a.date.localeCompare(b.date));
}
function renderHolidays() {
  const rows = holidayRows();
  $("#holList").innerHTML = rows.length ? rows.map(r => `<label class="holrow${r.done ? " done" : ""}"><input type="checkbox" data-hol="${r.date}" data-reason="${esc(r.reason)}" ${r.done ? "disabled" : "checked"}><time>${cap(DAY_SHORT[dow(r.date)])} ${fmtDate(r.date, true)}</time><span>${esc(r.reason)}${r.done ? " · už zapsáno" : ""}</span></label>`).join("")
    : `<p class="hint">Na pravidelné termíny této skupiny nepadají žádné prázdniny ani svátky.</p>`;
}
$("#holBtn").onclick = () => {
  if (!canWrite) return;
  $("#holIntro").textContent = `Termíny této skupiny, které ve školním roce ${yearLabel()} padnou na prázdniny nebo státní svátek. Zaškrtnuté se označí jako odpadlé i s důvodem. Jarní prázdniny se liší podle okresu, proto vyber jejich týden.`
    + (SCHOOL_HOLIDAYS[SY] ? "" : " Pro tento rok jsou v seznamu jen státní svátky – podzimní, vánoční, pololetní a velikonoční prázdniny označ v kalendáři ručně.");
  $("#holSpring").min = `${SY + 1}-02-01`; $("#holSpring").max = `${SY + 1}-03-20`; $("#holSpring").value = "";
  renderHolidays(); $("#dlgHol").showModal();
};
$("#holSpring").addEventListener("change", renderHolidays);
$("#fHol").addEventListener("submit", e => {
  if (e.submitter?.value === "cancel") return;
  const picked = [...document.querySelectorAll("#holList [data-hol]:checked")];
  picked.forEach(c => write("cancelled/" + c.dataset.hol, d => d.set({ date: c.dataset.hol, reason: c.dataset.reason })));
  if (picked.length) toast(`Označeno jako odpadlé: ${picked.length}`);
});

/* backup: readable Excel or a complete JSON copy of both groups */
function groupData(g) {
  const prev = G; G = g;
  try {
    const st = allStudents(), ss = sessions(), stateWord = { p: "přítomen", a: "nepřítomen", u: "", x: "nenastoupil" };
    const fam = s => S.family.get(s.id) || {};
    const dr = drop();
    const stuHead = ["Příjmení", "Jméno", ...(dr ? ["Třída", "Třídní učitel"] : []), "Přezdívka", "Role", "Stav", "Poznámka"].concat(canWrite ? ["Telefon žáka", "E-mail žáka", "Rodič 1", "Telefon", "E-mail", "Rodič 2", "Telefon", "E-mail"] : []);
    const stuRows = st.map(s => { const f = fam(s); return [s.surname, s.first, ...(dr ? [s.cls || "", s.teacher || ""] : []), s.nick || "", s.role || "", s.inactive ? "neaktivní" : "aktivní", s.note || ""]
      .concat(canWrite ? [f.contact?.phone || "", f.contact?.email || "", f.parent1?.name || "", f.parent1?.phone || "", f.parent1?.email || "", f.parent2?.name || "", f.parent2?.phone || "", f.parent2?.email || ""] : []); });
    const attHead = ["Příjmení", "Jméno", ...(dr ? ["Třída"] : []), ...ss.map(s => fmtDate(s.date, true)), dr ? "Přišel (×)" : "Účast %"];
    const attRows = st.map(s => { const r = stats(s.id); return [s.surname, s.first, ...(dr ? [s.cls || ""] : []), ...ss.map(x => dr ? (x.att?.[s.id] === "p" ? "přišel" : "") : stateWord[x.att?.[s.id] || "u"]), dr ? r.p : r.pct == null ? "" : r.pct]; });
    const offRows = fridays().filter(f => f.state === "off").map(f => [fmtDate(f.date, true), DAY[dow(f.date)], f.off.reason || ""]);
    const projRows = [...S.projects.values()].map(p => [p.name, STATUS[p.status] || "", p.progress || 0,
      (p.members || []).map(m => { const s = S.students.get(m.id); return s ? `${s.surname} ${s.first}${m.role ? " (" + m.role + ")" : ""}` : ""; }).filter(Boolean).join(", "),
      p.desc || "", (p.log || []).map(l => `${fmtDate(l.date, true)}: ${l.text}${l.photo ? " [fotka]" : ""}`).join("\n")]);
    const raw = { settings: { slots: slots() } };
    GCOLS.forEach(k => raw[k] = [...D[g][k].values()]);
    return { stu: [stuHead, ...stuRows], att: [attHead, ...attRows], off: [["Datum", "Den", "Důvod"], ...offRows],
      proj: [["Projekt", "Stav", "Hotovo %", "Tým", "Popis", "Průběh"], ...projRows], raw };
  } finally { G = prev; }
}
$("#backupBtn").onclick = () => { $("#restoreBox").hidden = !canWrite; $("#restorePrev").innerHTML = ""; $("#dlgBackup").showModal(); };
$("#histBtn").onclick = openHistory;

/* restore from a JSON backup (admins): preview first, then overwrite, optionally removing extra records */
const COL_NAME = { students: "Studenti", sessions: "Schůzky", projects: "Projekty", cancelled: "Odpadlé termíny", family: "Kontakty žáků" };
let restoreData = null;
$("#restoreFile").addEventListener("change", async e => {
  const file = e.target.files[0]; e.target.value = ""; if (!file) return;
  let data;
  try { data = JSON.parse(await file.text()); } catch { $("#restorePrev").innerHTML = `<p class="hint">Soubor není platná záloha (.json).</p>`; return; }
  if (!data || typeof data !== "object" || !data.groups || typeof data.groups !== "object") { $("#restorePrev").innerHTML = `<p class="hint">V souboru chybí data přehledu. Vyber zálohu z tlačítka Záloha nebo soubor zaloha.json.</p>`; return; }
  restoreData = data;
  const rows = [];
  for (const g in GROUP) for (const k of GCOLS) {
    const arr = Array.isArray(data.groups[g]?.[k]) ? data.groups[g][k] : [];
    rows.push(`<tr><td>${GROUP[g].short} · ${COL_NAME[k]}</td><td class="num">${D[g][k].size}</td><td class="num">${arr.length}</td></tr>`);
  }
  rows.push(`<tr><td>Kontakty (sdílené)</td><td class="num">${S.contacts.size}</td><td class="num">${Array.isArray(data.contacts) ? data.contacts.length : 0}</td></tr>`);
  const when = data.exported ? new Date(data.exported).toLocaleString("cs-CZ") : "neznámé datum";
  $("#restorePrev").innerHTML = `<p class="hint">Záloha z: <b>${esc(when)}</b></p>
    <table class="rtable"><thead><tr><th></th><th>Teď</th><th>V záloze</th></tr></thead><tbody>${rows.join("")}</tbody></table>
    <label class="chk"><input type="checkbox" id="restoreWipe"><span><b>Smazat i záznamy, které v záloze nejsou</b><small>Bez zaškrtnutí se záznamy jen přepíšou a doplní, nic navíc se nemaže.</small></span></label>
    <button class="btn danger" type="button" id="restoreGo">Obnovit ze zálohy</button>`;
});
$("#restorePrev").addEventListener("click", async e => {
  const b = e.target.closest("#restoreGo"); if (!b || !restoreData || !canWrite) return;
  if (!b.classList.contains("armed")) { b.classList.add("armed"); b.textContent = "Opravdu přepsat data zálohou?"; return; }
  b.disabled = true; b.textContent = "Obnovuji…";
  const wipe = $("#restoreWipe").checked, clean = o => { const { id, ...r } = o || {}; return r; };
  const ops = [];
  try {
    for (const g in GROUP) {
      const gd = restoreData.groups[g] || {};
      for (const k of GCOLS) {
        const arr = (Array.isArray(gd[k]) ? gd[k] : []).filter(x => x && typeof x.id === "string" && /^[A-Za-z0-9_.~:@+-]{1,200}$/.test(x.id));
        const keep = new Set(arr.map(x => x.id));
        arr.forEach(x => ops.push(() => db.doc(`${colName(g, k)}/${x.id}`).set(clean(x))));
        if (wipe) [...D[g][k].keys()].filter(id => !keep.has(id)).forEach(id => ops.push(() => db.doc(`${colName(g, k)}/${id}`).delete()));
      }
      if (gd.settings && typeof gd.settings === "object") ops.push(() => db.doc("settings/" + g).set(gd.settings));
    }
    const cs = (Array.isArray(restoreData.contacts) ? restoreData.contacts : []).filter(x => x && typeof x.id === "string");
    const keepC = new Set(cs.map(x => x.id));
    cs.forEach(x => ops.push(() => db.doc("contacts/" + x.id).set(clean(x))));
    if (wipe) [...S.contacts.keys()].filter(id => !keepC.has(id)).forEach(id => ops.push(() => db.doc("contacts/" + id).delete()));
    for (let i = 0; i < ops.length; i += 8) await Promise.all(ops.slice(i, i + 8).map(f => f()));
    db.collection("history").doc().set({ at: Date.now(), path: "-", op: "restore", before: null, label: `Obnova ze zálohy (${ops.length} záznamů)`, undone: true }).catch(() => {});
    toast(`Obnoveno: ${ops.length} záznamů.`); $("#dlgBackup").close();
  } catch { b.disabled = false; b.textContent = "Obnovit ze zálohy"; toast("Obnova se nepovedla celá. Zkus to znovu."); }
});
$("#fBackup").addEventListener("submit", async e => {
  if (e.submitter?.value === "cancel") return;
  const kind = document.querySelector("input[name=bkind]:checked").value;
  const groups = Object.fromEntries(Object.keys(GROUP).map(g => [g, groupData(g)]));
  const contacts = [...S.contacts.values()];
  if (kind === "json") {
    const out = { app: "Kroužek DuklaLabs", exported: new Date().toISOString(), contacts, groups: Object.fromEntries(Object.entries(groups).map(([g, x]) => [g, x.raw])) };
    return saveFile(`Krouzek_zaloha_${today}.json`, JSON.stringify(out, null, 2));
  }
  if (!window.XLSX) { try { toast("Připravuji Excel…"); await loadScript("https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"); } catch { return toast("Knihovnu pro Excel se nepodařilo načíst."); } }
  const wb = XLSX.utils.book_new();
  const add = (name, rows) => { const ws = XLSX.utils.aoa_to_sheet(rows); ws["!cols"] = rows[0].map((_, i) => ({ wch: i < 2 ? 16 : 14 })); XLSX.utils.book_append_sheet(wb, ws, name); };
  for (const [g, x] of Object.entries(groups)) {
    const p = GROUP[g].short;
    add(`${p} studenti`, x.stu); add(`${p} docházka`, x.att); add(`${p} odpadlo`, x.off); add(`${p} projekty`, x.proj);
  }
  add("Kontakty", [["Jméno", "Skupina", "Funkce", "Telefon", "E-mail", "Poznámka"], ...contacts.map(c => [c.name, c.type === "other" ? (c.group || "Další") : CTYPE[c.type] || "", c.role || "", c.phone || "", c.email || "", c.note || ""])]);
  saveFile(`Krouzek_zaloha_${today}.xlsx`, XLSX.write(wb, { type: "array", bookType: "xlsx" }));
});

function applyRO() {
  $("#ro").hidden = canWrite;
  ["#addSession", "#addProject", "#addStudent", "#addContact", "#holBtn", "#histBtn"].forEach(s => $(s).hidden = !canWrite);
  render();
}

/* ---------- data ---------- */
function setSync(ok, msg) { const el = $("#sync"); el.classList.toggle("ok", ok); el.querySelector("span").textContent = msg; }
// shim implementing just the Firestore-like surface this file calls (collection().doc().set/update/delete/get,
// onSnapshot, orderBy().limit().get(), doc(path)) on top of the REST API at /api/club/*. No real-time push on
// the server, so onSnapshot polls every 4s instead of receiving a push.
function createDb() {
  const API = BASE + "/api/club";
  async function apiFetch(path, opts) {
    const res = await fetch(API + path, { credentials: "include", ...opts });
    if (!res.ok) {
      const err = new Error("HTTP " + res.status);
      if (res.status === 401 || res.status === 403) err.code = "invalid_argument";
      throw err;
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : null;
  }
  function docRef(collection, id) {
    const theId = id || (window.crypto?.randomUUID ? window.crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
    return {
      id: theId,
      set: data => apiFetch(`/${collection}/${encodeURIComponent(theId)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
      update: data => apiFetch(`/${collection}/${encodeURIComponent(theId)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
      delete: () => apiFetch(`/${collection}/${encodeURIComponent(theId)}`, { method: "DELETE" }),
      get: async () => {
        const rows = await apiFetch(`/${collection}`);
        const row = (rows || []).find(r => String(r.id) === String(theId));
        return { exists: !!row, id: theId, data: () => row || {} };
      },
    };
  }
  function collectionRef(name) {
    return {
      doc: id => docRef(name, id),
      orderBy: () => ({
        limit: () => ({
          get: async () => {
            const rows = await apiFetch(`/history?limit=150`);
            return { docs: (rows || []).map(r => ({ id: String(r.id), data: () => r })) };
          },
        }),
      }),
      get: async () => {
        const rows = await apiFetch(`/${name}`);
        return { docs: (rows || []).map(r => ({ id: r.id, data: () => r })) };
      },
      onSnapshot: (onNext, onError) => {
        let stopped = false;
        const poll = async () => {
          if (stopped) return;
          try {
            const rows = await apiFetch(`/${name}`);
            const docs = (rows || []).map(r => ({ id: r.id, data: () => r }));
            onNext({ docs, size: docs.length, metadata: { fromCache: false } });
          } catch (e) { if (onError) onError(e); }
        };
        poll();
        const h = setInterval(poll, 4000);
        return () => { stopped = true; clearInterval(h); };
      },
    };
  }
  return {
    collection: collectionRef,
    doc: path => { const i = path.indexOf("/"); return docRef(path.slice(0, i), path.slice(i + 1)); },
  };
}
render();
(async () => {
  let whoami = null;
  try { const r = await fetch(BASE + "/api/whoami", { credentials: "include" }); if (r.ok) whoami = await r.json(); } catch {}
  db = createDb();
  if (!whoami) { setSync(false, "Data se ukážou po přihlášení"); canWrite = false; applyRO(); return; }
  canWrite = whoami.role === "admin" || whoami.role === "staff";
  if (!canWrite) applyRO();
  const timer = setTimeout(() => setSync(false, "Data se zatím nepodařilo načíst…"), 10000);
  const total = Object.keys(GROUP).length * GCOLS.length + 2;
  const done = key => { S.loaded.add(key); if (S.loaded.size === total) { clearTimeout(timer); setSync(true, "Uloženo a sdíleno"); } };
  const fail = () => { clearTimeout(timer); setSync(false, "Spojení s daty se přerušilo, obnov stránku."); };
  const sub = (name, map, key) => db.collection(name).onSnapshot(snap => {
    map.clear(); snap.docs.forEach(d => map.set(d.id, { id: d.id, ...d.data() }));
    if (snap.size || !snap.metadata.fromCache) S.got.add(key);
    if (!snap.metadata.fromCache) done(key);
    render();
  }, fail);
  for (const g in GROUP) GCOLS.forEach(k => sub(colName(g, k), D[g][k], g + ":" + k));
  sub("contacts", S.contacts, "contacts");
  // per-group settings (regular weekday): settings/zs, settings/ss
  db.collection("settings").onSnapshot(snap => {
    snap.docs.forEach(d => { const x = d.data(); if (D[d.id]) Object.assign(D[d.id], { weekday: x.weekday ?? null, start: x.start || null, end: x.end || null, slots: Array.isArray(x.slots) ? x.slots : null }); });
    if (!snap.metadata.fromCache) done("settings");
    render();
  }, fail);
})();
