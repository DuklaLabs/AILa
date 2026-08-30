// Studentská registrační mřížka – celý týden (Po–Pá × hodiny) jako v admin
// panelu, přepínač Tento / Příští týden. Zeleně ✓ jsou hodiny, na které je
// student už přihlášený (lze se z nich i odhlásit).

const state = { weekOffset: 0 };
let slotMap = {};      // slotMap[date][hour] = slot
let mine = new Set();  // open_hour_id, kam je student přihlášený

function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

async function renderGrid() {
    const monday = addDays(mondayOf(new Date()), state.weekOffset * 7);
    const from = isoDate(monday);
    const to = isoDate(addDays(monday, 4));

    document.querySelectorAll(".week-toggle button").forEach(b => {
        b.classList.toggle("active", Number(b.dataset.week) === state.weekOffset);
    });

    const [slots, periods, myIds] = await Promise.all([
        fetch(`/api/open-hours/list?from=${from}&to=${to}`).then(r => r.json()).catch(() => []),
        fetchPeriods(),
        fetch("/api/my-bookings").then(r => (r.ok ? r.json() : [])).catch(() => []),
    ]);

    mine = new Set(Array.isArray(myIds) ? myIds : []);

    slotMap = {};
    (Array.isArray(slots) ? slots : []).forEach(s => {
        if (s.hour_number === null || s.hour_number === undefined) return;
        (slotMap[s.date] ||= {})[s.hour_number] = s;
    });

    document.getElementById("weekGrid").innerHTML =
        buildWeekGrid(monday, periods, cellHtml);
}

function cellHtml(date, hour) {
    const slot = (slotMap[date] || {})[hour];
    if (!slot) return "";

    if (mine.has(slot.id)) {
        return `
            <div class="tt-slot tt-free tt-mine">
                <div class="tt-spots">✓ Přihlášen/a</div>
                ${slot.note ? `<div class="tt-note">${esc(slot.note)}</div>` : ""}
                <button class="tt-book tt-cancel-book" onclick="cancelHour(${slot.id})">Odhlásit</button>
            </div>
        `;
    }

    const full = slot.free_spots <= 0;
    return `
        <div class="tt-slot ${full ? "tt-full" : "tt-free"}">
            <div class="tt-spots">${full ? "Obsazeno" : slot.free_spots + " volných"}</div>
            ${slot.note ? `<div class="tt-note">${esc(slot.note)}</div>` : ""}
            <button class="btn-primary tt-book" onclick="bookHour(${slot.id})" ${full ? "disabled" : ""}>
                ${full ? "—" : "Registrovat"}
            </button>
        </div>
    `;
}

async function bookHour(id) {
    const res = await fetch("/api/book-hour", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hour_id: id }),
    });
    if (res.status === 401) {
        alert("Musíš být přihlášený/á.");
        window.location.href = "/login";
        return;
    }
    const reply = await res.json().catch(() => ({}));
    if (!res.ok) {
        alert(reply.detail || "Registrace se nezdařila.");
        return;
    }
    renderGrid();
}

async function cancelHour(id) {
    if (!confirm("Opravdu se odhlásit z této hodiny?")) return;
    const res = await fetch(`/api/book-hour/${id}`, { method: "DELETE" });
    if (res.status === 401) {
        window.location.href = "/login";
        return;
    }
    const reply = await res.json().catch(() => ({}));
    if (!res.ok) {
        alert(reply.detail || "Odhlášení se nezdařilo.");
        return;
    }
    renderGrid();
}

document.querySelectorAll(".week-toggle button").forEach(b => {
    b.addEventListener("click", () => {
        state.weekOffset = Number(b.dataset.week);
        renderGrid();
    });
});

renderGrid();
