async function loadHours() {
    const [slotsRes, periods] = await Promise.all([
        fetch("/api/open-hours/list"),
        fetchPeriods(),
    ]);
    const data = await slotsRes.json();

    if (!Array.isArray(data)) {
        document.getElementById("hoursList").innerHTML =
            "<p>❌ Nepodařilo se načíst otevřené hodiny.</p>";
        return;
    }

    document.getElementById("hoursList").innerHTML = buildOpenHoursGrid(data, periods, slot => {
        const full = slot.free_spots <= 0;
        return `
            <div class="tt-slot ${full ? "tt-full" : "tt-free"}">
                <div class="tt-spots">${full ? "Obsazeno" : slot.free_spots + " volných"}</div>
                <button class="btn-primary tt-book" onclick="bookHour(${slot.id})" ${full ? "disabled" : ""}>
                    ${full ? "—" : "Registrovat"}
                </button>
            </div>
        `;
    });
}

async function bookHour(id) {
    const res = await fetch("/api/book-hour", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hour_id: id })
    });

    if (res.status === 401) {
        alert("Musíš být přihlášený/á.");
        window.location.href = "/login";
        return;
    }

    const reply = await res.json();
    alert(reply.detail || "Hotovo!");
    loadHours();
}

loadHours();
