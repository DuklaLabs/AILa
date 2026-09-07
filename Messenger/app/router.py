from fastapi import APIRouter

from app.mailer import get_mailer
from app.models import SendRequest

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/send")
def send(req: SendRequest):
    return get_mailer().send(
        req.to,
        req.subject,
        req.body,
        html=req.html,
        cc=req.cc,
        bcc=req.bcc,
        ics=req.ics,
        ics_name=req.ics_name,
        ics_method=req.ics_method,
    )


# Zpětná kompatibilita se šablonovým rozhraním /task.
@router.post("/task")
def handle_task(data: dict):
    return get_mailer().send(
        data.get("to"),
        data.get("subject", ""),
        data.get("body", ""),
        html=bool(data.get("html", False)),
        cc=data.get("cc"),
        bcc=data.get("bcc"),
    )
