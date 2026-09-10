// Rozesílání e-mailů k uvolnění z výuky. V ostré verzi to bude dělat plánovač.
async function postDigest(url, btn) {
    const out = document.getElementById("digestResult");
    btn.disabled = true;
    out.textContent = " Odesílám…";
    try {
        const res = await fetch(url, { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            out.textContent = " " + (data.detail || "Chyba při odesílání.");
            return;
        }
        const sent = data.sent || [];
        const errs = data.errors || [];
        const who = sent
            .map(s => s.name || s.supervisor)
            .filter(Boolean)
            .join(", ");
        let msg = ` Odesláno: ${sent.length}`;
        if (who) msg += ` (${who})`;
        if (errs.length) msg += ` · chyby: ${errs.length}`;
        if (!sent.length && !errs.length) msg += " · nic k odeslání";
        out.textContent = msg;
    } catch (err) {
        out.textContent = " Chyba spojení.";
    } finally {
        btn.disabled = false;
    }
}

document.getElementById("sendDigestBtn")?.addEventListener("click", (e) =>
    postDigest("/api/decisions/send-digest", e.currentTarget));

document.getElementById("sendRosterBtn")?.addEventListener("click", (e) =>
    postDigest("/api/decisions/send-supervisor-roster", e.currentTarget));
