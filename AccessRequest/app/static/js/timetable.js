// Sdílený vykreslovač týdenní mřížky (dny × vyučovací hodiny), používá ho
// jak studentská rezervace, tak admin panel — každá stránka si jen předá
// vlastní funkci pro obsah buňky (cellHtmlFn).

const WEEKDAY_LABELS = ["Ne", "Po", "Út", "St", "Čt", "Pá", "So"];

function ttWeekdayLabel(dateStr) {
    const d = new Date(dateStr + "T00:00:00");
    return WEEKDAY_LABELS[d.getDay()];
}

function ttDateLabel(dateStr) {
    const d = new Date(dateStr + "T00:00:00");
    return `${d.getDate()}.${d.getMonth() + 1}.`;
}

function ttTime(t) {
    return (t || "").slice(0, 5);
}

async function fetchPeriods() {
    const res = await fetch("/api/open-hours/periods");
    return res.json();
}

// --- date helpers (used by the admin weekly grid) ---

function mondayOf(d) {
    const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const day = x.getDay();                 // 0 = Ne, 1 = Po …
    const diff = (day === 0 ? -6 : 1 - day); // posun na pondělí
    x.setDate(x.getDate() + diff);
    return x;
}

function addDays(d, n) {
    const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    x.setDate(x.getDate() + n);
    return x;
}

function isoDate(d) {
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${m}-${day}`;
}

// Vždy vykreslí celou kostru Po–Pá × vyučovací hodiny (i prázdné buňky).
// cellFn(dateStr, hourNumber) vrací HTML obsahu buňky.
function buildWeekGrid(monday, periods, cellFn) {
    let html = '<div class="timetable-wrap"><table class="timetable"><tr><th></th>';
    periods.forEach(p => {
        html += `
            <th class="tt-period">
                <div class="tt-num">${p.hour_number}</div>
                <div class="tt-time">${ttTime(p.start_time)}–${ttTime(p.end_time)}</div>
            </th>
        `;
    });
    html += "</tr>";

    for (let i = 0; i < 5; i++) {
        const date = isoDate(addDays(monday, i));
        html += `
            <tr>
                <th class="tt-day">
                    <div>${ttWeekdayLabel(date)}</div>
                    <div class="tt-date">${ttDateLabel(date)}</div>
                </th>
        `;
        periods.forEach(p => {
            html += `<td class="tt-cell">${cellFn(date, p.hour_number)}</td>`;
        });
        html += "</tr>";
    }

    html += "</table></div>";
    return html;
}

function buildOpenHoursGrid(slots, periods, cellHtmlFn) {
    const byDate = {};
    slots.forEach(s => {
        if (s.hour_number === null || s.hour_number === undefined) return;
        if (!byDate[s.date]) byDate[s.date] = {};
        byDate[s.date][s.hour_number] = s;
    });

    const dates = Object.keys(byDate).sort();

    if (dates.length === 0) {
        return "<p>Žádné otevřené hodiny zatím nejsou vypsané.</p>";
    }

    let html = '<div class="timetable-wrap"><table class="timetable"><tr><th></th>';
    periods.forEach(p => {
        html += `
            <th class="tt-period">
                <div class="tt-num">${p.hour_number}</div>
                <div class="tt-time">${ttTime(p.start_time)}–${ttTime(p.end_time)}</div>
            </th>
        `;
    });
    html += "</tr>";

    dates.forEach(date => {
        html += `
            <tr>
                <th class="tt-day">
                    <div>${ttWeekdayLabel(date)}</div>
                    <div class="tt-date">${ttDateLabel(date)}</div>
                </th>
        `;
        periods.forEach(p => {
            const slot = byDate[date][p.hour_number];
            html += `<td class="tt-cell">${slot ? cellHtmlFn(slot) : ""}</td>`;
        });
        html += "</tr>";
    });

    html += "</table></div>";
    return html;
}
