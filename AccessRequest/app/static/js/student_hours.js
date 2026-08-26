async function loadHours() {
    const res = await fetch("/api/open-hours/list");
    const data = await res.json();

    if (!Array.isArray(data)) {
        document.getElementById("hoursList").innerHTML =
            "<p>❌ Nepodařilo se načíst otevřené hodiny.</p>";
        return;
    }

    let html = `
        <table>
            <tr>
                <th>Datum</th>
                <th>Od</th>
                <th>Do</th>
                <th>Volná místa</th>
                <th></th>
            </tr>
    `;

    data.forEach(h => {
        const full = h.free_spots <= 0;
        html += `
            <tr>
                <td>${h.date}</td>
                <td>${h.start_time}</td>
                <td>${h.end_time}</td>
                <td>${full ? "Obsazeno" : h.free_spots}</td>
                <td>
                    <button class="btn-primary" onclick="bookHour(${h.id})" ${full ? "disabled" : ""}>
                        ${full ? "Obsazeno" : "Registrovat"}
                    </button>
                </td>
            </tr>
        `;
    });

    html += "</table>";

    document.getElementById("hoursList").innerHTML = html;
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
