// Drobné pomocné funkce sdílené mezi admin stránkami (Otevřené hodiny,
// Uživatelé, Analytika). Načítat jako první script na stránce.

function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

// krátké nenáročné potvrzení dole uprostřed (sdílený .toast) – vyžaduje #toastHost na stránce.
function toast(message, type = "success") {
    const host = document.getElementById("toastHost");
    if (!host) return;
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = message;
    const remove = () => el.remove();
    el.addEventListener("click", remove);
    host.appendChild(el);
    setTimeout(remove, 2500);
}

// Obecný detailní dialog (<dialog id="ohModal">) – obsah si naplní volající
// karta (open_hours.js, agent_reports.js), tohle ho jen otevírá / zavírá.
// Escape zavírá nativní <dialog>.
function openOhModal() {
    const modal = document.getElementById("ohModal");
    if (modal && !modal.open) modal.showModal();
}

function closeOhModal() {
    const modal = document.getElementById("ohModal");
    if (modal && modal.open) modal.close();
}
