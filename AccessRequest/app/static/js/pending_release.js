// Studenti čekající na souhlas s uvolňováním z výuky. Koordinátor (admin/staff)
// tu může svou část souhlasu udělit/odebrat; třídní učitel to dělá z e-mailu.
function relState(v) {
    return v === true ? "ANO" : v === false ? "NE" : "čeká";
}

async function loadPendingRelease() {
    const res = await fetch("/api/students/release-pending");
    if (!res.ok) return;
    const rows = await res.json();
    const card = document.getElementById("releaseCard");
    const list = document.getElementById("releaseList");
    document.getElementById("releaseCount").textContent = rows.length;
    if (!rows.length) { card.style.display = "none"; return; }
    card.style.display = "block";

    let html = `<table><tr><th>Student</th><th>Třída</th><th>Třídní učitel</th>
        <th>Třídní</th><th>Koordinátor</th><th></th></tr>`;
    rows.forEach(s => {
        html += `<tr>
            <td>${s.first_name} ${s.last_name}</td>
            <td>${s.class_group ?? ""}</td>
            <td>${s.release_class_teacher || "<span class='hint'>nezjištěn</span>"}</td>
            <td>${relState(s.release_teacher_ok)}</td>
            <td>${relState(s.release_coord_ok)}</td>
            <td>
              <button class="btn-primary" onclick="coordRelease(${s.student_id}, true)">Schválit</button>
              <button class="delete-btn" onclick="coordRelease(${s.student_id}, false)">Zamítnout</button>
            </td></tr>`;
    });
    list.innerHTML = html + "</table>";
}

async function coordRelease(studentId, ok) {
    const res = await fetch(`/api/students/${studentId}/release-coord`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ok }),
    });
    if (!res.ok) { alert("Nepodařilo se uložit."); return; }
    loadPendingRelease();
}

loadPendingRelease();
