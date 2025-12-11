import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict

def group_by_teacher(records):
    grouped = defaultdict(list)
    for r in records:
        grouped[r["teacher_name"]].append(r)
    return grouped


def format_email_for_teacher(teacher, lessons):
    message = f"Dobrý den,\n\nzde je týdenní přehled žáků uvolněných pro projekt DuklaLabs:\n\n"

    for l in lessons:
        full_name = f"{l['first_name']} {l['last_name']}"
        date = l["lesson_date"]
        hour = l["hour_number"]
        subject = l["subject_name"]

        message += f"- {date}, hodina {hour}, předmět {subject} – student: {full_name}\n"

    message += "\nPokud s uvolněním nesouhlasíte, prosím odpovězte na tento email.\n"
    message += "\nS pozdravem,\nDuklaLabs systém"

    return message


def send_email(to_addr, subject, body, from_addr, password):
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.office365.com", 465) as server:
        server.login(from_addr, password)
        server.sendmail(from_addr, to_addr, msg.as_string())


def agent_send_teacher_reports(db_records):
    # 1) seskupení podle učitele
    grouped = group_by_teacher(db_records)

    responses = []

    for teacher_name, lessons in grouped.items():
        # !!! zde je místo, kde dáš skutečný mail učitele
        teacher_email = lookup_teacher_email(teacher_name)

        body = format_email_for_teacher(teacher_name, lessons)

        send_email(
            to_addr=teacher_email,
            subject="Uvolnění studentů – týdenní přehled",
            body=body,
            from_addr="dukla@skola.cz",
            password="SMTP_HESLO"
        )

        responses.append({
            "teacher": teacher_name,
            "email": teacher_email,
            "count": len(lessons),
            "status": "sent"
        })

    return responses


# Simulace lookupu učitele – tady dáš DB nebo CSV
def lookup_teacher_email(teacher_name):
    mapping = {
        "Mgr. Bc. Jiří Hána": "hana@spssecb.cz",
        "Mgr. Pavlína Šustrová": "sustrova@spssecb.cz"
    }
    return mapping.get(teacher_name, "info@spssecb.cz")
