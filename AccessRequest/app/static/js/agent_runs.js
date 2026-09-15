// Karta „Běhy a spouštění agentů".
//  - horní panel: tlačítko „Spustit teď" pro každého agenta (proxy na access-agents)
//  - tabulka: historie běhů z auditního logu (GET /api/agents/runs)

async function loadAgentRuns() {
    const card = document.getElementById("agentRunsCard");
    // registr agentů (když je služba access-agents dole, vrátí prázdno)
    let registry = { agents: [] };
    try {
        const rr = await fetch("/api/agents/registry");
        if (rr.status === 403) { card.style.display = "none"; return; } // bez oprávnění
        if (rr.ok) registry = await rr.json();
    } catch (e) { /* služba nedostupná */ }

    card.style.display = "block";
    const btnHost = document.getElementById("agentRunButtons");
    const agents = registry.agents || [];
    if (!agents.length) {
        btnHost.innerHTML = `<p class="hint">Služba access-agents není dostupná –
            ruční spuštění je teď mimo provoz.</p>`;
    } else {
        btnHost.innerHTML = `<div class="agent-run-buttons">` + agents.map(a =>
            `<button class="btn-primary" onclick="runAgentNow('${esc(a)}', this)">
                ▶ ${esc(agentLabel(a))}</button>`).join("") + `</div>`;
    }

    const res = await fetch("/api/agents/runs");
    const list = document.getElementById("agentRunsList");
    if (!res.ok) { list.innerHTML = ""; return; }
    const rows = await res.json();
    if (!rows.length) { list.innerHTML = `<p class="hint">Zatím žádné běhy.</p>`; return; }

    let html = `<table><tr><th>Kdy</th><th>Agent</th><th>Spuštění</th><th>Výsledek</th></tr>`;
    rows.forEach(r => {
        const d = r.detail || {};
        const trig = d.trigger === "manual" ? "ručně"
            : d.trigger === "scheduler" ? "plánovač" : (d.trigger || "");
        const rest = Object.entries(d).filter(([k]) => k !== "trigger")
            .map(([k, v]) => `${k}: ${v}`).join(", ");
        html += `<tr>
            <td>${esc(r.at ?? "")}</td>
            <td>${esc(agentLabel(r.action))}</td>
            <td>${esc(trig)}</td>
            <td>${esc(rest)}</td></tr>`;
    });
    list.innerHTML = html + "</table>";
}

async function runAgentNow(name, btn) {
    const ok = await confirmDialog(
        `Spustit agenta „${agentLabel(name)}" teď? Běh může trvat desítky sekund.`,
        "Spustit");
    if (!ok) return;

    const host = document.getElementById("agentRunButtons");
    host.querySelectorAll("button").forEach(b => { b.disabled = true; });
    const label = btn.textContent;
    btn.textContent = "Spouštím…";

    try {
        const res = await fetch(`/api/agents/run/${name}`, { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            errorDialog(data.detail || `Spuštění selhalo (${res.status}).`);
        } else {
            toast(`Agent „${agentLabel(name)}" doběhl.`);
        }
    } catch (e) {
        errorDialog("Nepodařilo se spojit se službou agentů.");
    } finally {
        btn.textContent = label;
        host.querySelectorAll("button").forEach(b => { b.disabled = false; });
    }
    loadAgentRuns();
    if (typeof loadAgentProposals === "function") loadAgentProposals();
    if (typeof loadAgentReports === "function") loadAgentReports();
}

document.addEventListener("DOMContentLoaded", loadAgentRuns);
