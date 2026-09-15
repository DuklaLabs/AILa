// Fronta návrhů a upozornění od agentní vrstvy (agent.proposals, module=access).
//   pending  – čeká na rozhodnutí člověka (Schválit / Zamítnout)
//   info     – jen na vědomí (Beru na vědomí → acknowledged)
//   ostatní  – vyřízené (historie)
// Detail návrhu se otevírá v modalu #ohModal (sdílený s open_hours.js).

let _agentProposals = [];

async function loadAgentProposals() {
    const res = await fetch("/api/agents/proposals?status=");
    if (!res.ok) return; // bez agent.proposal:review → karta zůstane skrytá
    _agentProposals = await res.json();

    const card = document.getElementById("agentProposalsCard");
    if (!_agentProposals.length) { card.style.display = "none"; return; }
    card.style.display = "block";

    const pending = _agentProposals.filter(r => r.status === "pending");
    const info = _agentProposals.filter(r => r.status === "info");
    const done = _agentProposals.filter(
        r => !["pending", "info"].includes(r.status));

    document.getElementById("agentProposalsCount").textContent = pending.length;

    const list = document.getElementById("agentProposalsList");
    let html = "";

    if (!pending.length && !info.length) {
        html += `<p class="hint">Nic nečeká na rozhodnutí.</p>`;
    }
    if (pending.length) {
        html += `<h3 class="agent-sub">Čeká na rozhodnutí (${pending.length})</h3>`;
        html += proposalTable(pending);
    }
    if (info.length) {
        html += `<h3 class="agent-sub">Na vědomí (${info.length})</h3>`;
        html += proposalTable(info);
    }
    if (done.length) {
        html += `<details class="agent-history"><summary>Historie (${done.length})</summary>`;
        html += proposalTable(done);
        html += `</details>`;
    }
    list.innerHTML = html;
}

function proposalTable(rows) {
    let html = `<table><tr><th>Kdy</th><th>Agent</th><th>Druh</th>
        <th>Shrnutí</th><th>Jistota</th><th>Stav</th><th></th></tr>`;
    rows.forEach(r => {
        const when = (r.created_at || "").toString().slice(0, 16).replace("T", " ");
        let acts = `<button class="btn-ghost" onclick="showAgentProposal(${r.id})">Detail</button>`;
        if (r.status === "pending") {
            acts += `
                <button class="btn-primary" onclick="reviewProposal(${r.id}, true, this)">Schválit</button>
                <button class="delete-btn" onclick="reviewProposal(${r.id}, false, this)">Zamítnout</button>`;
        } else if (r.status === "info") {
            acts += `<button class="btn-primary" onclick="ackProposal(${r.id}, this)">Beru na vědomí</button>`;
        }
        html += `<tr>
            <td>${when}</td>
            <td>${esc(agentLabel(r.agent))}</td>
            <td>${esc(kindLabel(r.kind))}</td>
            <td>${esc(r.summary ?? "")}</td>
            <td>${confBar(r.confidence)}</td>
            <td><span class="agent-stat agent-stat-${r.status}">${esc(r.status ?? "")}</span></td>
            <td class="agent-acts">${acts}</td></tr>`;
    });
    return html + "</table>";
}

// --- detail v modalu -----------------------------------------------------

function showAgentProposal(id) {
    const r = _agentProposals.find(p => p.id === id);
    const body = document.getElementById("ohModalBody");
    const modal = document.getElementById("ohModal");
    if (!r || !body || !modal) return;

    const p = r.payload || {};
    let inner = "";
    if (r.kind === "registration.approve") inner = renderRegistration(p);
    else if (r.kind === "open_hours.week_plan") inner = renderWeekPlan(p);
    else if (r.kind === "release.advice") inner = renderAdvice(p);
    else if (r.kind === "student.subject_release_alert") inner = renderSubjectAlert(p);

    body.innerHTML = `
        <h3>${esc(kindLabel(r.kind))}</h3>
        <p class="oh-meta">${esc(agentLabel(r.agent))} ·
            ${(r.created_at || "").toString().slice(0, 16).replace("T", " ")}
            ${r.confidence != null ? " · jistota " + confBar(r.confidence) : ""}</p>
        <p>${esc(r.summary ?? "")}</p>
        ${inner}
        <details class="agent-raw"><summary>Zobrazit surová data</summary>
            <pre>${esc(JSON.stringify(p, null, 2))}</pre></details>`;
    modal.style.display = "flex";
}

function checkRow(label, ok, okText = "ano", badText = "ne") {
    if (ok === null || ok === undefined)
        return `<li><span class="check neutral">?</span> ${esc(label)} – neověřeno</li>`;
    return `<li><span class="check ${ok ? "ok" : "bad"}">${ok ? "✓" : "✗"}</span>
        ${esc(label)} – ${ok ? okText : badText}</li>`;
}

function renderRegistration(p) {
    const c = p.checks || {};
    return `
        <ul class="agent-checks">
            ${checkRow("Školní e-mailová doména", c.domain_ok)}
            ${checkRow("Jméno a příjmení v očekávaném tvaru", c.name_ok)}
            ${checkRow("Třída existuje v rozvrhu", c.class_in_timetable)}
            ${checkRow("Třídní učitel dohledán", c.class_teacher_known)}
            ${checkRow("Není duplicita ve třídě", c.duplicate_in_class === true ? false
                       : c.duplicate_in_class === false ? true : null,
                       "ano", "pozor, stejné jméno už ve třídě je")}
        </ul>
        <p><strong>Doporučení agenta:</strong>
            ${p.suggestion === "ok" ? "vypadá v pořádku" : "k ruční kontrole"}</p>
        <p class="hint">E-mail: ${esc(p.email || "?")} · třída: ${esc(p.class_group || "?")}</p>`;
}

function renderWeekPlan(p) {
    const slots = p.slots || [];
    if (!slots.length) return `<p>Žádné navržené hodiny.</p>`;
    const rows = slots.map(s => `<tr>
        <td>${esc(s.date)}</td>
        <td>${esc(s.hour_number)}. h</td>
        <td>${esc(s.supervisor)}</td>
        <td>${esc(s.capacity)}</td>
        <td>${esc(s.reason || "")}</td></tr>`).join("");
    return `
        <p><strong>Týden od ${esc(p.week_monday || "?")}</strong>
            ${p.method ? `<span class="hint">(${esc(p.method)})</span>` : ""}</p>
        <table><tr><th>Datum</th><th>Hodina</th><th>Dozor</th><th>Kapacita</th><th>Důvod</th></tr>
            ${rows}</table>`;
}

function renderAdvice(p) {
    const ctx = p.context || {};
    const rec = p.recommendation || "zvazit";
    const cls = { povolit: "rec-ok", zamitnout: "rec-no", zvazit: "rec-maybe" }[rec] || "rec-maybe";
    const h = ctx.history || {};
    return `
        <p><span class="rec-badge ${cls}">${esc(rec)}</span></p>
        <p>${esc(p.reason || "")}</p>
        <ul class="agent-checks">
            <li>Student: ${esc(ctx.student || "?")} (${esc(ctx.class_group || "?")})</li>
            <li>Termín: ${esc(ctx.date || "?")} · ${esc(ctx.hour_number)}. h · předmět ${esc(ctx.subject || "—")}</li>
            <li>Koliduje s výukou: ${ctx.collides_with_lesson ? "ano" : "ne"}</li>
            <li>Souhlas s uvolněním: ${ctx.release_consent_ok ? "kompletní" : "chybí"}</li>
            <li>Obsazenost hodiny: ${esc(ctx.occupancy || "?")}</li>
            <li>Historie studenta: ${h.approved ?? 0}× povoleno / ${h.denied ?? 0}× zamítnuto,
                ${h.came ?? 0}× přišel / ${h.no_show ?? 0}× nepřišel</li>
            <li>Uvolnění z tohoto předmětu (streak): ${ctx.subject_streak ?? 0}</li>
        </ul>`;
}

function renderSubjectAlert(p) {
    const pend = (p.pending || []).map(x => `${x.date} (${x.hour_number}. h)`).join(", ");
    return `
        <p><strong>${esc(p.student_name || "?")}</strong>
            (${esc(p.class_group || "?")}) byl uvolněn z
            <strong>${esc(p.released_count)}</strong> hodin předmětu
            <strong>${esc(p.subject || "?")}</strong> (práh ${esc(p.threshold)}).</p>
        <p>Zapisuje si další hodiny kolidující se stejným předmětem: ${esc(pend || "—")}</p>`;
}

// --- akce --------------------------------------------------------------

async function reviewProposal(id, approve, btn) {
    const r = _agentProposals.find(p => p.id === id) || {};
    const what = kindLabel(r.kind);
    const ok = await confirmDialog(
        approve ? `Schválit „${what}" a provést odpovídající akci?`
                : `Zamítnout „${what}"?`,
        approve ? "Schválit" : "Zamítnout");
    if (!ok) return;

    setRowBusy(btn, true);
    const verb = approve ? "approve" : "reject";
    const res = await fetch(`/api/agents/proposals/${id}/${verb}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        setRowBusy(btn, false);
        errorDialog(data.detail || "Nepodařilo se uložit.");
        return;
    }
    if (approve) reportApplied(r.kind, data.applied || {});
    else toast("Návrh zamítnut.");
    loadAgentProposals();
}

async function ackProposal(id, btn) {
    setRowBusy(btn, true);
    const res = await fetch(`/api/agents/proposals/${id}/ack`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
    });
    if (!res.ok) {
        setRowBusy(btn, false);
        const e = await res.json().catch(() => ({}));
        errorDialog(e.detail || "Nepodařilo se uložit.");
        return;
    }
    toast("Vzato na vědomí.");
    loadAgentProposals();
}

function reportApplied(kind, applied) {
    if (kind === "registration.approve") {
        toast("Účet aktivován" +
            (applied.student_name ? ": " + applied.student_name : "") + ".");
    } else if (kind === "open_hours.week_plan") {
        const c = (applied.created || []).length;
        const s = (applied.skipped || []).length;
        toast(`Založeno ${c} hodin, přeskočeno ${s}.`);
        if (s) {
            const lines = applied.skipped.map(
                x => `• ${x.slot?.date ?? "?"} ${x.slot?.hour_number ?? "?"}. h – ${x.why}`);
            appDialog({
                title: "Přeskočené hodiny",
                message: lines.join("\n"),
                variant: "info",
            });
        }
    } else {
        toast("Návrh schválen.");
    }
}

function setRowBusy(btn, busy) {
    const row = btn?.closest?.("tr");
    if (!row) return;
    row.querySelectorAll("button").forEach(b => { b.disabled = busy; });
}

document.addEventListener("DOMContentLoaded", loadAgentProposals);
