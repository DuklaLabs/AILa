// Stránka Stroje (/machines) – registr a provozní stav. Čtení je otevřené
// každému přihlášenému; zápis (lab.machine:manage) zkouší API samo – pokud
// uživatel nemá oprávnění, ovládací prvky se jen neukážou (zjištěno přes
// /api/whoami, stejně jako na portálu).

const STATUS_LABEL = { idle: "Volný", running: "Běží", broken: "Porucha", offline: "Mimo provoz" };
const STATUS_ORDER = ["idle", "running", "broken", "offline"];
let canManage = false;

async function loadMachines() {
    const list = document.getElementById("machinesList");
    const addBtn = document.getElementById("addMachineBtn");

    try {
        const me = await fetch("/api/whoami").then(r => (r.ok ? r.json() : null));
        canManage = !!me && (me.role === "admin" || me.role === "staff");
    } catch {
        canManage = false;
    }
    addBtn.style.display = canManage ? "inline-block" : "none";

    const res = await fetch("/api/machines");
    if (!res.ok) {
        list.innerHTML = `<p class="mch-empty">Nepodařilo se načíst stroje (${res.status}).</p>`;
        return;
    }
    const rows = await res.json();
    if (!rows.length) {
        list.innerHTML = `<p class="mch-empty">Zatím žádné stroje v evidenci.</p>`;
        return;
    }
    list.innerHTML = `<div class="mch-grid">${rows.map(machineCard).join("")}</div>`;
}

function machineCard(m) {
    const label = STATUS_LABEL[m.status] || m.status;
    const updated = m.status_updated_at ? new Date(m.status_updated_at).toLocaleString("cs-CZ") : "";
    const actions = canManage
        ? `<div class="mch-actions">
             ${STATUS_ORDER.filter(s => s !== m.status).map(s =>
                 `<button class="btn-ghost" onclick="setStatus(${m.id}, '${s}')">${STATUS_LABEL[s]}</button>`
             ).join("")}
             <button class="delete-btn" onclick="removeMachine(${m.id}, '${esc(m.name)}')">Vyřadit</button>
           </div>`
        : "";
    return `
        <div class="mch-card">
            <div class="mch-card-head">
                <div>
                    <div class="mch-name">${esc(m.name)}</div>
                    <div class="mch-type">${esc(m.type)}</div>
                </div>
            </div>
            ${m.location ? `<div class="mch-location">📍 ${esc(m.location)}</div>` : ""}
            <div class="mch-status mch-status-${esc(m.status)}">
                <span class="mch-status-dot"></span>${esc(label)}
            </div>
            ${m.status_note ? `<div class="mch-note">${esc(m.status_note)}</div>` : ""}
            ${updated ? `<div class="mch-updated">aktualizováno ${esc(updated)}</div>` : ""}
            ${actions}
        </div>`;
}

async function setStatus(id, status) {
    let note = null;
    if (status === "broken") {
        note = prompt("Co se stalo? (nepovinné, zobrazí se u stroje)") || "";
    }
    const res = await fetch(`/api/machines/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, note }),
    });
    if (!res.ok) {
        toast("Nepodařilo se změnit stav.", "error");
        return;
    }
    toast(`Stav změněn na „${STATUS_LABEL[status]}“.`);
    loadMachines();
}

async function removeMachine(id, name) {
    if (!confirm(`Vyřadit stroj „${name}“ z evidence?`)) return;
    const res = await fetch(`/api/machines/${id}`, { method: "DELETE" });
    if (!res.ok) {
        toast("Nepodařilo se vyřadit stroj.", "error");
        return;
    }
    toast("Stroj vyřazen.");
    loadMachines();
}

document.getElementById("addMachineBtn").addEventListener("click", async () => {
    const name = prompt("Název stroje:");
    if (!name) return;
    const type = prompt("Typ (např. FDM tiskárna, Laser, CNC):") || "";
    const location = prompt("Umístění (nepovinné):") || null;

    const res = await fetch("/api/machines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, type, location }),
    });
    if (!res.ok) {
        toast("Nepodařilo se vytvořit stroj.", "error");
        return;
    }
    toast("Stroj přidán.");
    loadMachines();
});

loadMachines();
