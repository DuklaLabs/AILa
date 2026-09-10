// Historie měsíčních reportů o využívání laborky (agent.reports, module=access).
async function loadAgentReports() {
    const res = await fetch("/api/agents/reports");
    if (!res.ok) return; // chybí agent.report:read → karta zůstane skrytá
    const rows = await res.json();
    const card = document.getElementById("agentReportsCard");
    const list = document.getElementById("agentReportsList");
    if (!rows.length) { card.style.display = "none"; return; }
    card.style.display = "block";

    let html = `<table><tr><th>Období</th><th>Vygenerováno</th><th>Shrnutí</th><th></th></tr>`;
    rows.forEach(r => {
        html += `<tr>
            <td>${(r.period || "").toString().slice(0, 7)}</td>
            <td>${r.generated_at ?? ""}</td>
            <td>${(r.summary ?? "").slice(0, 160)}</td>
            <td><button class="btn-primary" onclick="showAgentReport(${r.id})">Detail</button></td>
        </tr>`;
    });
    list.innerHTML = html + "</table>";
}

async function showAgentReport(id) {
    const res = await fetch(`/api/agents/reports/${id}`);
    const box = document.getElementById("agentReportDetail");
    if (!res.ok) { box.textContent = "Nepodařilo se načíst."; return; }
    const r = await res.json();
    const p = r.payload || {};
    const subj = Object.entries(p.released_by_subject || {})
        .map(([k, v]) => `<li>${k}: ${v}</li>`).join("");
    const wo = (p.watch_outs || []).map(x => `<li>${x}</li>`).join("");
    box.innerHTML = `
        <hr>
        <h3>Report za ${(r.period || "").toString().slice(0, 7)}</h3>
        <p>${r.summary ?? ""}</p>
        ${wo ? `<p><strong>Na co si dát pozor:</strong></p><ul>${wo}</ul>` : ""}
        ${subj ? `<p><strong>Uvolněné hodiny podle předmětu:</strong></p><ul>${subj}</ul>` : ""}
        <pre style="white-space:pre-wrap;font-size:12px;background:#f6f6f6;padding:8px;border-radius:6px;">${
            JSON.stringify(p, null, 2)}</pre>`;
}

loadAgentReports();
