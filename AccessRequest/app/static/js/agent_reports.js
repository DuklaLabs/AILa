// Historie periodických reportů agentní vrstvy (agent.reports, module=access).
// Detail se otevírá v modalu #ohModal (sdílený s open_hours.js).

async function loadAgentReports() {
    const res = await fetch("/api/agents/reports");
    if (!res.ok) return; // bez agent.report:read → karta zůstane skrytá
    const rows = await res.json();
    const card = document.getElementById("agentReportsCard");
    const list = document.getElementById("agentReportsList");
    if (!rows.length) { card.style.display = "none"; return; }
    card.style.display = "block";

    let html = `<table><tr><th>Období</th><th>Vygenerováno</th><th>Shrnutí</th><th></th></tr>`;
    rows.forEach(r => {
        html += `<tr>
            <td>${esc((r.period || "").toString().slice(0, 7))}</td>
            <td>${esc(r.generated_at ?? "")}</td>
            <td>${esc((r.summary ?? "").slice(0, 160))}</td>
            <td><button class="btn-ghost" onclick="showAgentReport(${r.id})">Detail</button></td>
        </tr>`;
    });
    list.innerHTML = html + "</table>";
}

async function showAgentReport(id) {
    const body = document.getElementById("ohModalBody");
    const modal = document.getElementById("ohModal");
    if (!body || !modal) return;
    body.innerHTML = `<p>Načítám…</p>`;
    modal.style.display = "flex";

    const res = await fetch(`/api/agents/reports/${id}`);
    if (!res.ok) { body.innerHTML = `<p class="oh-empty">Nepodařilo se načíst.</p>`; return; }
    const r = await res.json();
    const p = r.payload || {};

    const subj = Object.entries(p.released_by_subject || {})
        .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("");
    const wo = (p.watch_outs || []).map(x => `<li>${esc(x)}</li>`).join("");

    body.innerHTML = `
        <h3>Report za ${esc((r.period || "").toString().slice(0, 7))}</h3>
        <p class="oh-meta">vygenerováno ${esc(r.generated_at ?? "")}</p>
        <p>${esc(r.summary ?? "")}</p>
        ${wo ? `<p><strong>Na co si dát pozor:</strong></p><ul class="agent-checks">${wo}</ul>` : ""}
        ${subj ? `<p><strong>Uvolněné hodiny podle předmětu:</strong></p>
            <table><tr><th>Předmět</th><th>Počet</th></tr>${subj}</table>` : ""}
        <details class="agent-raw"><summary>Zobrazit surová data</summary>
            <pre>${esc(JSON.stringify(p, null, 2))}</pre></details>`;
}

document.addEventListener("DOMContentLoaded", loadAgentReports);
