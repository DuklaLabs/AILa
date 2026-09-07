import psycopg2
import re
import requests
from config import DB_CONFIG, MESSENGER_URL


# ==================================================
# TOOL: SQL dotaz
# ==================================================
def db_query(query: str) -> dict:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(query)

    try:
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, row)) for row in rows]
    except:
        result = "OK"

    conn.commit()
    cur.close()
    conn.close()
    print ("DB_QUERY RESULT:", result)
    return {"result": result}


# ==================================================
# TOOL: Odesílání e-mailu (přes službu Messenger / Microsoft Graph)
# ==================================================
def send_email(to: str, subject: str, body: str) -> dict:
    try:
        resp = requests.post(
            f"{MESSENGER_URL}/send",
            json={"to": to, "subject": subject, "body": body},
            timeout=20,
        )
    except requests.RequestException as e:
        return {"status": "ERROR", "message": f"Messenger nedostupný: {e}"}

    if resp.status_code != 200:
        return {
            "status": "ERROR",
            "message": f"Messenger vrátil {resp.status_code}: {resp.text}",
        }
    return resp.json()


# ==================================================
# TOOL: Týdenní report učitelům
# ==================================================
def generate_weekly_report(teacher_name: str, lessons: list) -> dict:
    text = f"Dobrý den {teacher_name},\n\n"
    text += "Zde je týdenní přehled studentů uvolněných pro projekt DuklaLabs:\n\n"

    for l in lessons:
        s = f"{l['first_name']} {l['last_name']}"
        text += f"- {l['lesson_date']} | hodina {l['hour_number']} | {l['subject_name']} → {s}\n"

    text += (
        "\nPokud s uvolněním nesouhlasíte, odpovězte prosím na tento email.\n"
        "Stačí napsat: NESOUHLASÍM – Jan Novák.\n\n"
        "S pozdravem,\nDuklaLabs systém"
    )

    return {"email_text": text}


# ==================================================
# TOOL: Stav e-mailu studentovi
# ==================================================
def generate_student_status_email(first_name: str, last_name: str, lessons: list) -> dict:
    text = f"Ahoj {first_name},\n\n"
    text += "Zde máš přehled o stavu tvých žádostí o uvolnění:\n\n"

    for l in lessons:
        teacher = l["teacher_name"]
        subject = l["subject_name"]
        date = l["lesson_date"]
        hour = l["hour_number"]
        approved = l["approved"]

        status = (
            "SCHVÁLENO ✔️" if approved is True
            else "ZAMÍTNUTO ❌" if approved is False
            else "ČEKÁ NA SCHVÁLENÍ ⏳"
        )

        text += f"- {date} | hodina {hour} | {subject} (učitel {teacher}) → {status}\n"

    text += "\nHezký den,\nDuklaLabs systém"
    return {"email_text": text}


# ==================================================
# TOOL: Zpracování odpovědi učitele (NESOUHLASÍM)
# ==================================================
def process_teacher_reply(email_body: str) -> dict:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    email_body_lower = email_body.lower()

    if "nesouhlas" not in email_body_lower:
        return {"status": "ignored"}

    pattern = r"([A-ZÁČĎÉŘŠŤÚŮÝŽ][a-záčďéěíóřšťúůýž]+ [A-ZÁČĎÉŘŠŤÚŮÝŽ][a-záčďéěíóřšťúůýž]+)"
    matches = re.findall(pattern, email_body)

    rejected = []

    for fullname in matches:
        first, last = fullname.split(" ", 1)
        cur.execute("""
            UPDATE internal.excused
            SET approved = FALSE
            WHERE student_id = (
                SELECT student_id FROM internal.students
                WHERE first_name = %s AND last_name = %s
            )
        """, (first, last))
        rejected.append(fullname)

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "processed", "students": rejected}
