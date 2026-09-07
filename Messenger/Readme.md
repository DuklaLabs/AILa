# Messenger – odesílání e-mailů

Služba pro odesílání e-mailů. Má dva backendy podle `MAIL_BACKEND`:

- **`graph`** (cílový stav) – Microsoft Graph API `sendMail`, OAuth2
  client-credentials (app-only), odesílání z **petrasek@spssecb.cz**. Basic SMTP
  AUTH Microsoft plošně vypíná, proto Graph.
- **`smtp`** (dočasně pro testy) – klasické SMTP, typicky Gmail. Umožňuje testovat
  celý řetězec hned, než IT školy dokončí registraci aplikace v Entra ID.

Přepnutí backendu = změna jediné proměnné `MAIL_BACKEND` v `Messenger/.env`.

## Architektura

- `app/mailer.py` – samostatné jádro. Žádné FastAPI/agent závislosti, jde
  importovat i spustit z CLI. Řeší získání a cache tokenu + volání `sendMail`.
- `app/router.py` – FastAPI obal: `POST /send`, `POST /task` (zpětná kompat.),
  `GET /health`.
- `app/config.py` – čtení env proměnných.
- Ostatní služby (např. `Security_agent`) volají `POST http://messenger:8005/send`.

## Konfigurace (env)

| Proměnná           | Popis                                                        |
|--------------------|------------------------------------------------------------- |
| `MAIL_BACKEND`     | `graph` nebo `smtp` (default `graph`)                        |
| `MS_TENANT_ID`     | Directory (tenant) ID z Entra ID (backend `graph`)          |
| `MS_CLIENT_ID`     | Application (client) ID registrované aplikace                |
| `MS_CLIENT_SECRET` | Client secret value                                          |
| `MAIL_SENDER`      | Schránka odesílatele pro Graph (default `petrasek@spssecb.cz`) |
| `SMTP_HOST`/`SMTP_PORT` | SMTP server (default `smtp.gmail.com` / `587`)          |
| `SMTP_USER`/`SMTP_PASSWORD` | Přihlášení k SMTP (u Gmailu app password)           |
| `SMTP_FROM`/`SMTP_FROM_NAME` | Nepovinné; `SMTP_FROM` default = `SMTP_USER`       |
| `MAIL_ENABLED`     | `false` → `/send` vrací `{"status":"DISABLED"}`              |
| `MAIL_DRY_RUN`     | `true` → neodesílá, vrací sestavený payload                 |
| `AGENT_PORT`       | Port služby (default `8005`)                                 |

Zkopíruj `.env.example` do `.env` a doplň hodnoty. `.env` je v `.gitignore`.

## Co musí zařídit IT školy (Entra ID)

1. **App registration** (single-tenant) v tenantu `spssecb.cz`.
2. **API permission:** Microsoft Graph → *Application permissions* →
   **`Mail.Send`** → **Grant admin consent**.
3. **Client secret** – vygenerovat, poznamenat expiraci (6/12/24 měs.).
4. Předat: **Directory (tenant) ID**, **Application (client) ID**,
   **client secret value**.
5. **Application Access Policy** – omezit aplikaci jen na schránku
   `petrasek@spssecb.cz` (jinak může app posílat jako kdokoli v tenantu):

   ```powershell
   New-ApplicationAccessPolicy -AppId <CLIENT_ID> `
     -PolicyScopeGroupId petrasek@spssecb.cz `
     -AccessRight RestrictAccess -Description "AILa Messenger – jen odesílání"
   ```

## Ruční test

```bash
# dry-run bez credentials
MAIL_DRY_RUN=true python -m app.mailer --to nekdo@spssecb.cz --subject Test --body Ahoj

# ostrý test po doplnění .env
python -m app.mailer --to muj@druhy.mail --subject "AILa test" --body "funguje"
```

Přes službu:

```bash
curl -X POST localhost:8005/send -H "Content-Type: application/json" \
  -d '{"to":"x@y.cz","subject":"t","body":"b"}'
```
