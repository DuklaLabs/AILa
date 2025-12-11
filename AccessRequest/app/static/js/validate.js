function validateStudentForm() {
    const fn = document.getElementById("first_name").value.trim();
    const ln = document.getElementById("last_name").value.trim();
    const em = document.getElementById("email").value.trim();
    const cg = document.getElementById("class_group").value;

    if (fn.length < 2) {
        alert("Jméno je příliš krátké.");
        return false;
    }
    if (ln.length < 2) {
        alert("Příjmení je příliš krátké.");
        return false;
    }
    if (!em.includes("@") || !em.includes(".")) {
        alert("Neplatný e-mail.");
        return false;
    }
    if (!cg || cg === "") {
    alert("Vyber třídu.");
    return false;
}


    const loader = document.getElementById("loader");
    if (loader) loader.classList.remove("hidden");

    return true; // povolí odeslání formuláře
}
