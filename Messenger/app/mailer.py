"""
Samostatný modul pro odesílání e-mailů.

Dva backendy, přepínač ``MAIL_BACKEND``:
  * ``graph`` – Microsoft Graph API ``sendMail`` (OAuth2 client-credentials,
    app-only). Cílový stav – odesílání z firemní schránky petrasek@spssecb.cz.
    Aplikace musí být zaregistrovaná v Entra ID s oprávněním ``Mail.Send``
    a admin consentem (viz Messenger/Readme.md).
  * ``smtp`` – klasické SMTP (např. Gmail). Slouží k testování, než bude
    hotová registrace v Entra ID.

Žádné FastAPI ani agent závislosti – jde importovat i spustit z CLI:

    python -m app.mailer --to nekdo@example.com --subject "Test" --body "Ahoj"
"""

from __future__ import annotations

import os
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional, Sequence

import base64
from email import encoders
from email.mime.base import MIMEBase

import httpx

_AUTHORITY = "https://login.microsoftonline.com"
_GRAPH = "https://graph.microsoft.com/v1.0"
_SCOPE = "https://graph.microsoft.com/.default"
_TOKEN_LEEWAY = 60  # obnovit token 60 s před vypršením


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "ano"}


class MailerError(RuntimeError):
    """Chyba při získání tokenu nebo odeslání e-mailu."""


@dataclass
class MailerConfig:
    backend: str = "graph"  # "graph" | "smtp"

    # -- Microsoft Graph --
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    sender: str = "petrasek@spssecb.cz"

    # -- SMTP --
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # default = smtp_user
    smtp_from_name: str = ""

    # -- společné --
    enabled: bool = True
    dry_run: bool = False
    # Bezpečnostní brzda pro testování: když je vyplněno, VŠECHNA pošta jde jen
    # na tuto adresu (původní příjemci se propíšou do předmětu a těla).
    redirect_to: str = ""

    @classmethod
    def from_env(cls) -> "MailerConfig":
        return cls(
            backend=os.getenv("MAIL_BACKEND", "graph").strip().lower(),
            redirect_to=os.getenv("MAIL_REDIRECT_TO", "").strip(),
            tenant_id=os.getenv("MS_TENANT_ID", ""),
            client_id=os.getenv("MS_CLIENT_ID", ""),
            client_secret=os.getenv("MS_CLIENT_SECRET", ""),
            sender=os.getenv("MAIL_SENDER", "petrasek@spssecb.cz"),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            # Gmail app password se zobrazuje po skupinách s mezerami – ty do
            # loginu nepatří, takže je odstraníme.
            smtp_password=os.getenv("SMTP_PASSWORD", "").replace(" ", ""),
            smtp_from=os.getenv("SMTP_FROM", ""),
            smtp_from_name=os.getenv("SMTP_FROM_NAME", ""),
            enabled=_env_bool("MAIL_ENABLED", True),
            dry_run=_env_bool("MAIL_DRY_RUN", False),
        )

    def require_graph_credentials(self) -> None:
        missing = [
            n
            for n, v in (
                ("MS_TENANT_ID", self.tenant_id),
                ("MS_CLIENT_ID", self.client_id),
                ("MS_CLIENT_SECRET", self.client_secret),
            )
            if not v
        ]
        if missing:
            raise MailerError(
                "Chybí konfigurace Microsoft Graph: " + ", ".join(missing)
            )

    def require_smtp_credentials(self) -> None:
        missing = [
            n
            for n, v in (
                ("SMTP_HOST", self.smtp_host),
                ("SMTP_USER", self.smtp_user),
                ("SMTP_PASSWORD", self.smtp_password),
            )
            if not v
        ]
        if missing:
            raise MailerError("Chybí konfigurace SMTP: " + ", ".join(missing))

    @property
    def from_address(self) -> str:
        return self.smtp_from or self.smtp_user


def _recipients(addresses: Sequence[str]) -> list[dict]:
    return [{"emailAddress": {"address": a}} for a in addresses if a]


def _as_list(value: Optional[Sequence[str] | str]) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


@dataclass
class Mailer:
    config: MailerConfig = field(default_factory=MailerConfig.from_env)
    timeout: float = 15.0

    _token: Optional[str] = field(default=None, init=False, repr=False)
    _token_exp: float = field(default=0.0, init=False, repr=False)

    # -- token (Graph) -----------------------------------------------------
    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_exp - _TOKEN_LEEWAY:
            return self._token

        self.config.require_graph_credentials()
        url = f"{_AUTHORITY}/{self.config.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "scope": _SCOPE,
        }
        try:
            resp = httpx.post(url, data=data, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise MailerError(f"Nedostupný token endpoint: {exc}") from exc

        if resp.status_code != 200:
            raise MailerError(
                f"Token request selhal ({resp.status_code}): {resp.text}"
            )

        payload = resp.json()
        self._token = payload["access_token"]
        self._token_exp = now + float(payload.get("expires_in", 3600))
        return self._token

    # -- payload (Graph) -------------------------------------------------
    def build_payload(
        self,
        to: Sequence[str] | str,
        subject: str,
        body: str,
        *,
        html: bool = False,
        cc: Optional[Sequence[str] | str] = None,
        bcc: Optional[Sequence[str] | str] = None,
        ics: Optional[str] = None,
        ics_name: str = "udalost.ics",
        ics_method: str = "PUBLISH",
    ) -> dict:
        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML" if html else "Text",
                "content": body,
            },
            "toRecipients": _recipients(_as_list(to)),
        }
        if cc:
            message["ccRecipients"] = _recipients(_as_list(cc))
        if bcc:
            message["bccRecipients"] = _recipients(_as_list(bcc))
        if ics:
            message["attachments"] = [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": ics_name,
                "contentType": f"text/calendar; method={ics_method}",
                "contentBytes": base64.b64encode(ics.encode("utf-8")).decode(),
            }]
        return {"message": message, "saveToSentItems": True}

    # -- send ------------------------------------------------------------
    def send(
        self,
        to: Sequence[str] | str,
        subject: str,
        body: str,
        *,
        html: bool = False,
        cc: Optional[Sequence[str] | str] = None,
        bcc: Optional[Sequence[str] | str] = None,
        ics: Optional[str] = None,
        ics_name: str = "udalost.ics",
        ics_method: str = "PUBLISH",
    ) -> dict:
        to_l, cc_l, bcc_l = _as_list(to), _as_list(cc), _as_list(bcc)
        att = dict(ics=ics, ics_name=ics_name, ics_method=ics_method)

        redirected_from = None
        redirected_to = None
        if self.config.redirect_to:
            orig = ", ".join([*to_l, *cc_l, *bcc_l]) or "(nikdo)"
            redirected_from = orig
            redirected_to = self.config.redirect_to
            note = f"[Původně určeno: {orig}]"
            body = (
                f"<p style=\"color:#b42318;font-weight:600;\">{note}</p>{body}"
                if html
                else f"{note}\n\n{body}"
            )
            subject = f"{subject}  » pův. {orig}"
            to_l, cc_l, bcc_l = [self.config.redirect_to], [], []

        if not self.config.enabled:
            return {"status": "DISABLED"}
        if self.config.dry_run:
            return {
                "status": "DRY_RUN",
                "backend": self.config.backend,
                "redirected_from": redirected_from,
                "redirected_to": redirected_to,
                "payload": self.build_payload(
                    to_l, subject, body, html=html, cc=cc_l, bcc=bcc_l, **att
                ),
            }

        try:
            if self.config.backend == "smtp":
                result = self._send_smtp(to_l, subject, body, html, cc_l, bcc_l, **att)
            else:
                result = self._send_graph(to_l, subject, body, html, cc_l, bcc_l, **att)
        except MailerError as exc:
            result = {"status": "ERROR", "message": str(exc)}
        if redirected_from is not None:
            result["redirected_from"] = redirected_from
            result["redirected_to"] = redirected_to
        return result

    def _send_graph(self, to, subject, body, html, cc, bcc,
                    ics=None, ics_name="udalost.ics", ics_method="PUBLISH") -> dict:
        payload = self.build_payload(
            to, subject, body, html=html, cc=cc, bcc=bcc,
            ics=ics, ics_name=ics_name, ics_method=ics_method,
        )
        try:
            token = self._get_token()
            url = f"{_GRAPH}/users/{self.config.sender}/sendMail"
            resp = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            return {"status": "ERROR", "message": f"Graph nedostupný: {exc}"}

        if resp.status_code == 202:
            return {"status": "OK", "backend": "graph"}
        return {
            "status": "ERROR",
            "message": f"Graph sendMail selhal ({resp.status_code}): {resp.text}",
        }

    def _send_smtp(self, to, subject, body, html, cc, bcc,
                   ics=None, ics_name="udalost.ics", ics_method="PUBLISH") -> dict:
        self.config.require_smtp_credentials()

        msg = MIMEMultipart()
        from_addr = self.config.from_address
        msg["From"] = (
            formataddr((self.config.smtp_from_name, from_addr))
            if self.config.smtp_from_name
            else from_addr
        )
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html" if html else "plain", "utf-8"))
        if ics:
            part = MIMEBase("text", "calendar", method=ics_method, name=ics_name)
            part.set_payload(ics.encode("utf-8"))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=ics_name)
            msg.attach(part)

        envelope_to = [*to, *cc, *bcc]
        try:
            if self.config.smtp_port == 465:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self.config.smtp_host, self.config.smtp_port,
                    timeout=self.timeout, context=ctx,
                ) as server:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.sendmail(from_addr, envelope_to, msg.as_string())
            else:
                with smtplib.SMTP(
                    self.config.smtp_host, self.config.smtp_port,
                    timeout=self.timeout,
                ) as server:
                    server.starttls(context=ssl.create_default_context())
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.sendmail(from_addr, envelope_to, msg.as_string())
        except (smtplib.SMTPException, OSError) as exc:
            return {"status": "ERROR", "message": f"SMTP selhalo: {exc}"}

        return {"status": "OK", "backend": "smtp"}


# -- modulová zkratka se sdílenou instancí -------------------------------
_default: Optional[Mailer] = None


def get_mailer() -> Mailer:
    global _default
    if _default is None:
        _default = Mailer()
    return _default


def send_email(to: Sequence[str] | str, subject: str, body: str, **kwargs) -> dict:
    """Odešle e-mail přes sdílenou instanci Maileru."""
    return get_mailer().send(to, subject, body, **kwargs)


# -- CLI ---------------------------------------------------------------
def _main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Odeslat e-mail (Graph nebo SMTP).")
    parser.add_argument("--to", required=True, action="append", help="příjemce (lze zopakovat)")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--html", action="store_true", help="tělo je HTML")
    parser.add_argument("--cc", action="append", default=None)
    parser.add_argument("--bcc", action="append", default=None)
    args = parser.parse_args(argv)

    result = get_mailer().send(
        args.to, args.subject, args.body,
        html=args.html, cc=args.cc, bcc=args.bcc,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"OK", "DRY_RUN", "DISABLED"} else 1


if __name__ == "__main__":
    raise SystemExit(_main())
