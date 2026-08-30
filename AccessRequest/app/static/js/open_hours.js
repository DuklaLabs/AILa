// Admin: interaktivní týdenní mřížka pro zadávání otevřených hodin.
// Řádky Po–Pá × sloupce vyučovacích hodin (0–10). V každé buňce je buď "+"
// (přidat volnou hodinu inline formulářem), nebo už zadaná volná hodina
// (editace kapacity/poznámky, smazání). Do prázdných buněk se propisují
// hodiny dozorujících učitelů z oddělené duklamaps DB – každý dozor jako
// samostatný barevný blok, s možností je ve filtru zapnout/vypnout.

const state = {
    weekOffset: 0,
    activeSupervisors: null,   // Set<string> | null (null = ještě nenačteno)
};
let slotMap = {};    // slotMap[date][hour] = slot
let supMap = {};     // supMap[date][hour] = [supervision, ...] (po filtru chipů)
let supAllMap = {};  // totéž bez filtru – pro zákaz dozora v inline formuláři
let supNames = [];   // pořadí dozorů z configu
const SUP_COLORS = ["#eab308", "#38bdf8", "#a78bfa", "#f472b6", "#34d399", "#fb923c"];

function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

// krátké nenáročné potvrzení v rohu (úspěch)
function toast(message, type = "success") {
    const host = document.getElementById("toastHost");
    if (!host) return;
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = message;
    const remove = () => el.remove();
    el.addEventListener("click", remove);
    host.appendChild(el);
    setTimeout(remove, 2500);
}

// celoobrazovkové okno; vrací Promise s hodnotou stisknutého tlačítka
function appDialog({ title, message, variant = "info", buttons }) {
    return new Promise(resolve => {
        const wrap = document.getElementById("appDialog");
        if (!wrap) {
            if (variant === "confirm") return resolve(confirm(message));
            alert(message);
            return resolve(true);
        }
        const box = wrap.querySelector(".app-dialog-box");
        box.className = `app-dialog-box app-dialog-${variant}`;
        document.getElementById("appDialogTitle").textContent = title || "";
        document.getElementById("appDialogMsg").textContent = message || "";

        const actions = document.getElementById("appDialogActions");
        actions.innerHTML = "";

        function done(value) {
            wrap.style.display = "none";
            document.removeEventListener("keydown", onKey);
            wrap.onclick = null;
            resolve(value);
        }
        function onKey(e) {
            if (e.key === "Escape") done(false);
            if (e.key === "Enter") done(true);
        }

        (buttons || [{ label: "Rozumím", value: true, primary: true }]).forEach(b => {
            const el = document.createElement("button");
            el.textContent = b.label;
            el.className = b.primary ? "btn-primary" : "app-dialog-cancel";
            el.onclick = () => done(b.value);
            actions.appendChild(el);
        });

        wrap.onclick = e => { if (e.target === wrap) done(false); };
        document.addEventListener("keydown", onKey);
        wrap.style.display = "flex";
        (actions.querySelector(".btn-primary") || actions.firstChild || {}).focus?.();
    });
}

function errorDialog(message) {
    return appDialog({ title: "Chyba", message, variant: "error" });
}

function confirmDialog(message, okLabel = "Potvrdit") {
    return appDialog({
        title: "Potvrzení",
        message,
        variant: "confirm",
        buttons: [
            { label: "Zrušit", value: false },
            { label: okLabel, value: true, primary: true },
        ],
    });
}

function supColor(name) {
    const i = supNames.indexOf(name);
    return SUP_COLORS[(i < 0 ? 0 : i) % SUP_COLORS.length];
}

// "Příští týden" = plánování (přidávání/úpravy), "Tento týden" = jen přehled
function editable() {
    return state.weekOffset === 1;
}

async function renderGrid() {
    const monday = addDays(mondayOf(new Date()), state.weekOffset * 7);
    const from = isoDate(monday);
    const to = isoDate(addDays(monday, 4));

    document.querySelectorAll(".week-toggle button").forEach(b => {
        b.classList.toggle("active", Number(b.dataset.week) === state.weekOffset);
    });

    const week = state.weekOffset === 1 ? "next" : "actual";
    const [slots, periods, sups, names] = await Promise.all([
        fetch(`/api/open-hours/list?from=${from}&to=${to}`).then(r => r.json()).catch(() => []),
        fetchPeriods(),
        fetch(`/api/open-hours/supervisions?from=${from}&to=${to}&week=${week}`)
            .then(r => (r.ok ? r.json() : [])).catch(() => []),
        fetch(`/api/open-hours/supervisors`)
            .then(r => (r.ok ? r.json() : [])).catch(() => []),
    ]);

    supNames = Array.isArray(names) ? names : [];
    if (state.activeSupervisors === null) {
        state.activeSupervisors = new Set(supNames);   // výchozí: všichni zapnutí
    }
    renderSupFilter();

    const hint = document.getElementById("gridHint");
    if (hint) {
        hint.innerHTML = editable()
            ? "Plánování: klikni na <strong>+</strong> pro přidání volné hodiny. Barevně je hodina dozorujícího učitele z rozvrhu."
            : "Přehled obsazení. Klikni na obsazenou hodinu a uvidíš, kdo má přijít a z jaké třídy.";
    }

    slotMap = {};
    (Array.isArray(slots) ? slots : []).forEach(s => {
        if (s.hour_number === null || s.hour_number === undefined) return;
        (slotMap[s.date] ||= {})[s.hour_number] = s;
    });

    supMap = {};
    supAllMap = {};
    (Array.isArray(sups) ? sups : []).forEach(l => {
        if (!l.date || l.hour_number === null || l.hour_number === undefined) return;
        ((supAllMap[l.date] ||= {})[l.hour_number] ||= []).push(l);
        if (state.activeSupervisors && !state.activeSupervisors.has(l.supervisor)) return;
        ((supMap[l.date] ||= {})[l.hour_number] ||= []).push(l);
    });

    document.getElementById("weekGrid").innerHTML =
        buildWeekGrid(monday, periods, cellHtml);
}

function renderSupFilter() {
    const box = document.getElementById("supFilter");
    if (!box) return;
    if (supNames.length === 0) {
        box.innerHTML = "";
        box.style.display = "none";
        return;
    }
    box.style.display = "flex";
    box.innerHTML = `<span class="sup-filter-label">Dozor:</span>` + supNames.map((name, i) => {
        const on = state.activeSupervisors.has(name);
        return `<button class="sup-chip ${on ? "on" : ""}" style="--sup:${supColor(name)}"
                        onclick="toggleSupervisor(${i})">
                    <span class="sup-dot"></span>${esc(name)}
                </button>`;
    }).join("");
}

function toggleSupervisor(i) {
    const name = supNames[i];
    if (name === undefined) return;
    if (state.activeSupervisors.has(name)) state.activeSupervisors.delete(name);
    else state.activeSupervisors.add(name);
    renderGrid();
}

// bloky s výukou dozorů (z duklamaps) – zobrazují se i pod už zadanou
// volnou hodinou, aby ji hodina jiného kolegy nepřekryla
function supBlocksHtml(sups) {
    if (!sups.length) return "";
    const bySup = {};
    sups.forEach(s => (bySup[s.supervisor] ||= []).push(s));
    return supNames
        .filter(name => bySup[name])
        .map(name => {
            const rows = bySup[name];
            const subj = [...new Set(rows.map(s => s.subject_name).filter(Boolean))].join(", ");
            const cls = [...new Set(rows.map(s => s.class_name).filter(Boolean))].join(", ");
            const room = [...new Set(rows.map(s => s.room).filter(Boolean))].join(", ");
            const tip = `${name}: ` + rows.map(s =>
                `${s.subject_name} · ${s.class_name}${s.room ? " · " + s.room : ""}`).join("; ");
            return `
                <div class="tt-blocked" style="--sup:${supColor(name)}" title="${esc(tip)}">
                    <div class="tt-blocked-main">🔒 ${esc(subj || "Výuka")}</div>
                    <div class="tt-blocked-sub">${esc([cls, room].filter(Boolean).join(" · "))}</div>
                </div>
            `;
        }).join("");
}

function cellHtml(date, hour) {
    const slot = (slotMap[date] || {})[hour];
    const sups = (supMap[date] || {})[hour] || [];
    const canEdit = editable();
    const blocks = supBlocksHtml(sups);

    if (slot) {
        const full = slot.free_spots <= 0;
        const supList = parseSupervisors(slot.supervisor);
        const supLabel = supList.length
            ? `<div class="tt-slot-sups">${supList.map(n =>
                   `<span class="tt-slot-sup" style="--sup:${supColor(n)}">${esc(n)}</span>`
               ).join("")}</div>`
            : "";
        const slotHtml = !canEdit
            ? `
                <div class="tt-slot ${full ? "tt-full" : "tt-free"} tt-clickable"
                     title="Zobrazit přihlášené"
                     onclick="showBookings(${slot.id}, '${date}', ${hour})">
                    <div class="tt-spots">${slot.booked_count}/${slot.capacity}</div>
                    ${supLabel}
                    ${slot.note ? `<div class="tt-note">${esc(slot.note)}</div>` : ""}
                </div>
            `
            : `
                <div class="tt-slot ${full ? "tt-full" : "tt-free"}">
                    <button class="tt-edit" title="Upravit"
                            onclick="editSlot(${slot.id}, this)">✏️</button>
                    <button class="tt-del" title="Smazat"
                            onclick="deleteHour(${slot.id})">×</button>
                    <div class="tt-spots tt-clickable" title="Zobrazit přihlášené"
                         onclick="showBookings(${slot.id}, '${date}', ${hour})">${slot.booked_count}/${slot.capacity} obsazeno</div>
                    ${supLabel}
                    ${slot.note ? `<div class="tt-note">${esc(slot.note)}</div>` : ""}
                </div>
            `;
        return `<div class="tt-cellwrap">${slotHtml}${blocks}</div>`;
    }

    if (blocks) {
        return `
            <div class="tt-blocked-stack">
                ${blocks}
                ${canEdit ? `<button class="tt-add-sm" title="Přesto přidat volnou hodinu"
                        onclick="openAddForm('${date}', ${hour}, this)">+ přidat</button>` : ""}
            </div>
        `;
    }

    return canEdit
        ? `<button class="tt-add" title="Přidat volnou hodinu"
                   onclick="openAddForm('${date}', ${hour}, this)">+</button>`
        : "";
}

// --- přehled přihlášených (jen "tento týden") -----------------------

async function showBookings(id, date, hour) {
    const body = document.getElementById("ohModalBody");
    const modal = document.getElementById("ohModal");
    if (!body || !modal) {   // stará šablona bez modalu (nutný rebuild)
        errorDialog("Detail rezervací není k dispozici – zkus tvrdý reload (Ctrl+Shift+R).");
        return;
    }
    const slot = (slotMap[date] || {})[hour] || {};
    const head = `${ttWeekdayLabel(date)} ${ttDateLabel(date)} · ${hour}. hodina`;
    const meta = [
        slot.supervisor ? `Dozor: ${slot.supervisor}` : "",
        slot.note || "",
        (slot.capacity != null) ? `kapacita ${slot.capacity}` : "",
    ].filter(Boolean).join(" · ");
    const header = `<h3>${esc(head)}</h3>${meta ? `<p class="oh-meta">${esc(meta)}</p>` : ""}`;
    body.innerHTML = `${header}<p>Načítám…</p>`;
    modal.style.display = "flex";

    let rows;
    try {
        const res = await fetch(`/api/open-hours/${id}/bookings`);
        if (!res.ok) {
            const t = await res.text().catch(() => "");
            body.innerHTML = `${header}<p class="oh-empty">Chyba ${res.status}. ${esc(t.slice(0, 200))}</p>`;
            return;
        }
        rows = await res.json();
    } catch (e) {
        body.innerHTML = `${header}<p class="oh-empty">Nepodařilo se načíst: ${esc(String(e))}</p>`;
        return;
    }

    if (!Array.isArray(rows) || rows.length === 0) {
        body.innerHTML = `${header}<p class="oh-empty">Zatím nikdo přihlášený.</p>`;
        return;
    }

    body.innerHTML = `
        ${header.replace("</h3>", ` <span class="oh-count">${rows.length}×</span></h3>`)}
        <table class="oh-list">
            <tr><th>Jméno</th><th>Příjmení</th><th>Třída</th></tr>
            ${rows.map(r => `
                <tr>
                    <td>${esc(r.first_name || "")}</td>
                    <td>${esc(r.last_name || "")}</td>
                    <td>${esc(r.class_group || "—")}</td>
                </tr>
            `).join("")}
        </table>
    `;
}

function closeOhModal() {
    document.getElementById("ohModal").style.display = "none";
}

document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeOhModal();
});

// --- inline formuláře -------------------------------------------------

function inlineForm({ capacity, note, supervisors, blocked, onSave }) {
    const chosen = new Set(supervisors || []);
    const blockedSet = new Set(blocked || []);
    const supOptions = supNames.length
        ? `<div class="tt-sup-label">Dozor (povinné):</div><div class="tt-sup-multi">` + supNames.map(n => {
              const dis = blockedSet.has(n);
              const on = chosen.has(n) && !dis;
              return `<label class="tt-sup-opt ${on ? "on" : ""} ${dis ? "blocked" : ""}"
                             style="--sup:${supColor(n)}"
                             title="${dis ? "Má v tuto hodinu vlastní výuku" : ""}">
                   <input type="checkbox" class="tt-sup-cb" value="${esc(n)}"
                          ${on ? "checked" : ""} ${dis ? "disabled" : ""}
                          onchange="this.parentNode.classList.toggle('on', this.checked)">
                   <span>${esc(n)}${dis ? " – učí" : ""}</span>
               </label>`;
          }).join("") + `</div>`
        : "";
    return `
        <div class="tt-inline">
            <input type="number" class="tt-cap" min="1" value="${capacity}">
            ${supOptions}
            <input type="text" class="tt-note" placeholder="Poznámka" value="${esc(note)}">
            <div class="tt-inline-actions">
                <button class="btn-primary" onclick="${onSave}">Uložit</button>
                <button class="tt-cancel" onclick="renderGrid()">Zrušit</button>
            </div>
        </div>
    `;
}

function inlineSupervisorValue(cell) {
    return [...cell.querySelectorAll(".tt-sup-cb:checked")].map(cb => cb.value).join(", ");
}

// volná hodina musí mít aspoň jednoho dozora (když jsou nějací nakonfigurovaní)
async function supervisorRequiredOk(cell) {
    if (!supNames.length) return true;
    if (inlineSupervisorValue(cell)) return true;
    await errorDialog("Vyber aspoň jednoho dozora.");
    return false;
}

function parseSupervisors(value) {
    return (value || "").split(",").map(s => s.trim()).filter(Boolean);
}

function openAddForm(date, hour, btn) {
    const cell = btn.closest(".tt-cell");
    // dozor, který v té buňce sám učí, nesmí být zároveň dozorem → zakázat
    const blocked = [...new Set(((supAllMap[date] || {})[hour] || []).map(s => s.supervisor))];
    cell.dataset.date = date;
    cell.dataset.hour = hour;
    cell.innerHTML = inlineForm({
        capacity: 5,
        note: "",
        supervisors: [],
        blocked: blocked,
        onSave: "submitAdd(this)",
    });
    cell.querySelector(".tt-cap").focus();
}

async function submitAdd(btn) {
    const cell = btn.closest(".tt-cell");
    if (!(await supervisorRequiredOk(cell))) return;
    const capacity = cell.querySelector(".tt-cap").value;
    const note = cell.querySelector(".tt-note").value;

    const form = new FormData();
    form.append("date", cell.dataset.date);
    form.append("hour_number", cell.dataset.hour);
    form.append("capacity", capacity);
    form.append("note", note);
    form.append("supervisor", inlineSupervisorValue(cell));

    const res = await fetch("/api/open-hours/add", { method: "POST", body: form });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        await errorDialog(err.detail || "Nepodařilo se uložit.");
        return;
    }
    toast("Volná hodina přidána.");
    renderGrid();
}

function editSlot(id, btn) {
    const cell = btn.closest(".tt-cell");
    const slot = findSlotById(id);
    if (!slot) return renderGrid();
    const cellSups = (supAllMap[slot.date] || {})[slot.hour_number] || [];
    const blocked = [...new Set(cellSups.map(s => s.supervisor))];
    cell.innerHTML = inlineForm({
        capacity: slot.capacity,
        note: slot.note || "",
        supervisors: parseSupervisors(slot.supervisor),
        blocked: blocked,
        onSave: `submitEdit(${id}, this)`,
    });
    cell.querySelector(".tt-cap").focus();
}

async function submitEdit(id, btn) {
    const cell = btn.closest(".tt-cell");
    if (!(await supervisorRequiredOk(cell))) return;
    const capacity = cell.querySelector(".tt-cap").value;
    const note = cell.querySelector(".tt-note").value;

    const form = new FormData();
    form.append("capacity", capacity);
    form.append("note", note);
    form.append("supervisor", inlineSupervisorValue(cell));

    const res = await fetch(`/api/open-hours/${id}`, { method: "PATCH", body: form });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        await errorDialog(err.detail || "Nepodařilo se uložit.");
        return;
    }
    toast("Změny uloženy.");
    renderGrid();
}

async function deleteHour(id) {
    if (!(await confirmDialog("Opravdu smazat tuto otevřenou hodinu?", "Smazat"))) return;

    const res = await fetch(`/api/open-hours/delete/${id}`, { method: "DELETE" });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        await errorDialog(err.detail || "Nepodařilo se smazat.");
        return;
    }
    toast("Volná hodina smazána.");
    renderGrid();
}

function findSlotById(id) {
    for (const day of Object.values(slotMap)) {
        for (const slot of Object.values(day)) {
            if (slot.id === id) return slot;
        }
    }
    return null;
}

// --- přepínač týdnů -------------------------------------------------

document.querySelectorAll(".week-toggle button").forEach(b => {
    b.addEventListener("click", () => {
        state.weekOffset = Number(b.dataset.week);
        renderGrid();
    });
});

renderGrid();
