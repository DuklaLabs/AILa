async function loadOpenHours() {
    const [slotsRes, periods] = await Promise.all([
        fetch("/api/open-hours/list"),
        fetchPeriods(),
    ]);
    const data = await slotsRes.json();

    if (!Array.isArray(data)) {
        document.getElementById("openHoursList").innerHTML =
            "<p>❌ Nepodařilo se načíst data.</p>";
        return;
    }

    document.getElementById("openHoursList").innerHTML = buildOpenHoursGrid(data, periods, slot => `
        <div class="tt-slot ${slot.free_spots <= 0 ? "tt-full" : "tt-free"}">
            <button class="tt-del" onclick="deleteHour(${slot.id})" title="Smazat">×</button>
            <div class="tt-spots">${slot.free_spots}/${slot.capacity} volno</div>
            ${slot.note ? `<div class="tt-note">${slot.note}</div>` : ""}
        </div>
    `);
}

document.getElementById("openHoursForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const form = new FormData(e.target);

    const res = await fetch("/api/open-hours/add", {
        method: "POST",
        body: form
    });

    const msg = document.getElementById("formMessage");

    if (res.ok) {
        msg.innerHTML = "<span style='color:lime;'>✔ Hodina byla přidána</span>";
        e.target.reset();
        loadOpenHours();
    } else {
        const err = await res.json();
        msg.innerHTML = "<span style='color:red;'>❌ Chyba: " + err.detail + "</span>";
    }
});

async function deleteHour(id) {
    if (!confirm("Opravdu smazat tuto otevřenou hodinu?")) return;

    const res = await fetch(`/api/open-hours/delete/${id}`, { method: "DELETE" });
    if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Nepodařilo se smazat.");
        return;
    }
    loadOpenHours();
}

loadOpenHours();
