// Přátelské názvy agentů a druhů návrhů. Používá agent_runs.js
// (načíst tenhle soubor jako první).

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
