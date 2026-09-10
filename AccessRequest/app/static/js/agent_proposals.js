// Fronta návrhů/upozornění od agentní vrstvy (agent.proposals, module=access).
// "info" = jen na vědomí, "pending" = čeká na schválení člověkem.
async function loadAgentProposals() {
    const res = await fetch("/api/agents/proposals?status=");
    if (!res.ok) return; // nemá oprávnění agent.proposal:review → karta zůstane skrytá
    const rows = await res.json();
    const card = document.getElementById("agentProposalsCard");
    const list = document.getElementById("agentProposalsList");
    const open = rows.filter(r => r.status === "pending" || r.status === "info");
    document.getElementById("agentProposalsCount").textContent = open.length;
    if (!rows.length) { card.style.display = "none"; return; }
    card.style.display = "block";

    let html = `<table><tr><th>Kdy</th><th>Agent</th><th>Druh</th>
        <th>Shrnutí</th><th>Stav</th><th></th></tr>`;
    rows.forEach(r => {
        const when = (r.created_at || "").toString().slice(0, 16).replace("T", " ");
        const acts = r.status === "pending"
            ? `<button class="btn-primary" onclick="reviewProposal(${r.id}, true)">Schválit</button>
               <button class="delete-btn" onclick="reviewProposal(${r.id}, false)">Zamítnout</button>`
            : `<span class="hint">${r.status}</span>`;
        html += `<tr>
            <td>${when}</td>
            <td>${r.agent ?? ""}</td>
            <td>${r.kind ?? ""}</td>
            <td>${r.summary ?? ""}</td>
            <td>${r.status ?? ""}</td>
            <td>${acts}</td></tr>`;
    });
    list.innerHTML = html + "</table>";
}

async function reviewProposal(id, approve) {
    const verb = approve ? "approve" : "reject";
    const res = await fetch(`/api/agents/proposals/${id}/${verb}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
    });
    if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || "Nepodařilo se uložit.");
        return;
    }
    loadAgentProposals();
}

loadAgentProposals();
