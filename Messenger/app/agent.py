from app.mailer import get_mailer


def process_task(data: dict) -> dict:
    """Tenký obal nad Mailerem – přijme dict a odešle e-mail."""
    return get_mailer().send(
        data.get("to"),
        data.get("subject", ""),
        data.get("body", ""),
        html=bool(data.get("html", False)),
        cc=data.get("cc"),
        bcc=data.get("bcc"),
    )
