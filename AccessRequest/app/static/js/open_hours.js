async function loadOpenHours() {
    const res = await fetch("/api/open-hours/list");
    const data = await res.json();

    if (!Array.isArray(data)) {
        document.getElementById("openHoursList").innerHTML =
            "<p>❌ Nepodařilo se načíst data.</p>";
        return;
    }

    let html = `
        <table>
            <tr>
                <th>Datum</th>
                <th>Od</th>
                <th>Do</th>
                <th>Kapacita</th>
                <th>Poznámka</th>
                <th></th>
            </tr>
    `;

    data.forEach(item => {
        html += `
            <tr>
                <td>${item.date}</td>
                <td>${item.start_time}</td>
                <td>${item.end_time}</td>
                <td>${item.capacity}</td>
                <td>${item.note ?? ""}</td>
                <td>
                    <button class="delete-btn" onclick="deleteHour(${item.id})">Smazat</button>
                </td>
            </tr>
        `;
    });

    html += "</table>";
    document.getElementById("openHoursList").innerHTML = html;
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

    await fetch(`/api/open-hours/delete/${id}`, { method: "DELETE" });
    loadOpenHours();
}

loadOpenHours();
