// Přátelské názvy agentů a druhů návrhů. Sdílené mezi agent_proposals.js,
// agent_reports.js a agent_runs.js (načíst tenhle soubor jako první).

const AGENT_LABEL = {
    monthly_lab_report: "Měsíční report laborky",
    subject_release_watch: "Hlídač uvolnění dle předmětu",
    release_advisor: "Asistent rozhodování o uvolnění",
    registration_triage: "Triage registrací",
    openhours_planner: "Plánovač otevřených hodin",
};

const KIND_LABEL = {
    "registration.approve": "Aktivace studentského účtu",
    "open_hours.week_plan": "Plán otevřených hodin na týden",
    "release.advice": "Doporučení k uvolnění (na vědomí)",
    "student.subject_release_alert": "Opakované uvolnění z předmětu (na vědomí)",
};

// access.agent.registration_triage → registration_triage
function agentLabel(name) {
    const key = String(name || "").replace(/^access\.agent\./, "");
    return AGENT_LABEL[key] || key || "—";
}

function kindLabel(kind) {
    return KIND_LABEL[kind] || kind || "—";
}

// confidence 0..1 → mini proužek
function confBar(value) {
    if (value == null || isNaN(value)) return "";
    const pct = Math.round(Math.max(0, Math.min(1, Number(value))) * 100);
    return `<span class="conf-bar" title="jistota ${pct} %">
        <span class="conf-fill" style="width:${pct}%"></span></span>
        <span class="conf-num">${pct} %</span>`;
}
