// Log odeslaných e-mailů (messaging.mail_log) – ověření, že mail odešel.
const mailLogState = { flt: "" };

function mlEsc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

function mlStatus(s) {
    const color = { OK: "#1a7f37", ERROR: "#b42318", DRY_RUN: "#9a6700",
                    DISABLED: "#777" }[s] || "#333";
    return `<strong style="color:${color}">${mlEsc(s)}</strong>`;
}

async function loadMailLog() {
    const url = "/api/mail-log?limit=150" +
        (mailLogState.flt ? `&status=${mailLogState.flt}` : "");
    const res = await fetch(url);
    if (!res.ok) {
        document.getElementById("mailLogList").textContent =
            res.status === 403 ? "Jen pro admin/staff." : "Chyba načtení.";
        return;
    }
    const data = await res.json();
    const c = data.counts || {};
    document.getElementById("mailLogCounts").textContent =
        `OK: ${c.OK || 0} · chyby: ${c.ERROR || 0} · dry-run: ${c.DRY_RUN || 0}` +
        ` · vypnuto: ${c.DISABLED || 0}`;

    const rows = data.rows || [];
    if (!rows.length) {
        document.getElementById("mailLogList").textContent = "Zatím nic.";
        return;
    }
    let html = `<table><tr><th>Čas</th><th>Příjemce</th><th>Předmět</th>
        <th>Stav</th><th>Backend</th><th></th></tr>`;
    rows.forEach(r => {
        const to = (r.to_addrs || []).join(", ");
        const redir = r.delivered_to
            ? `<br><span class="hint">→ doručeno na ${mlEsc(r.delivered_to)}</span>` : "";
        const err = r.error
            ? `<br><span style="color:#b42318">${mlEsc(r.error)}</span>` : "";
        html += `<tr>
            <td style="white-space:nowrap">${mlEsc(r.created_at)}</td>
            <td>${mlEsc(to)}${redir}</td>
            <td>${mlEsc(r.subject)}${err}</td>
            <td>${mlStatus(r.status)}</td>
            <td>${mlEsc(r.backend || "")}</td>
            <td>${r.has_ics ? "📅" : ""}</td>
        </tr>`;
    });
    document.getElementById("mailLogList").innerHTML = html + "</table>";
}

document.querySelectorAll("#mailLogCard .week-toggle button").forEach(b => {
    b.addEventListener("click", () => {
        document.querySelectorAll("#mailLogCard .week-toggle button")
            .forEach(x => x.classList.toggle("active", x === b));
        mailLogState.flt = b.dataset.flt;
        loadMailLog();
    });
});

loadMailLog();
