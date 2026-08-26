async function loadPendingStudents() {
    const res = await fetch("/api/students/pending");
    if (!res.ok) return;

    const students = await res.json();
    const card = document.getElementById("pendingCard");
    const list = document.getElementById("pendingList");
    const count = document.getElementById("pendingCount");

    count.textContent = students.length;

    if (students.length === 0) {
        card.style.display = "none";
        return;
    }
    card.style.display = "block";

    let html = `
        <table>
            <tr>
                <th>Jméno</th>
                <th>Třída</th>
                <th>E-mail</th>
                <th>Registrace</th>
                <th></th>
            </tr>
    `;

    students.forEach(s => {
        html += `
            <tr>
                <td>${s.first_name} ${s.last_name}</td>
                <td>${s.class_group ?? ""}</td>
                <td>${s.email}</td>
                <td>${s.registration_date}</td>
                <td>
                    <button class="btn-primary" onclick="approveStudent(${s.user_id})">✔ Schválit</button>
                    <button class="delete-btn" onclick="rejectStudent(${s.user_id})">✘ Zamítnout</button>
                </td>
            </tr>
        `;
    });

    html += "</table>";
    list.innerHTML = html;
}

async function approveStudent(userId) {
    const res = await fetch(`/api/students/${userId}/approve`, { method: "POST" });
    if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Nepodařilo se schválit.");
        return;
    }
    loadPendingStudents();
}

async function rejectStudent(userId) {
    if (!confirm("Opravdu zamítnout a smazat tuto registraci?")) return;
    const res = await fetch(`/api/students/${userId}/reject`, { method: "POST" });
    if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Nepodařilo se zamítnout.");
        return;
    }
    loadPendingStudents();
}

loadPendingStudents();
