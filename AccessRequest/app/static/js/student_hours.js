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
                <th>Kapacita</th>
                <th></th>
            </tr>
    `;

    data.forEach(h => {
        html += `
            <tr>
                <td>${h.date}</td>
                <td>${h.start_time}</td>
                <td>${h.end_time}</td>
                <td>${h.capacity}</td>
                <td>
                    <button class="btn-primary" onclick="bookHour(${h.id})">
                        Registrovat
                    </button>
                </td>
            </tr>
        `;
    });

    html += "</table>";

    document.getElementById("hoursList").innerHTML = html;
}

async function bookHour(id) {
    const studentEmail = prompt("Zadejte svůj školní e-mail:");
    if (!studentEmail) return;

    const res = await fetch("/book-hour", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            hour_id: id,
            email: studentEmail
        })
    });

    const reply = await res.json();

    alert(reply.detail || "Hotovo!");
}

loadHours();
