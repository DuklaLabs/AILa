import os

# Který backend se použije: "graph" (cílový) nebo "smtp" (dočasně pro testy).
MAIL_BACKEND = os.getenv("MAIL_BACKEND", "graph")

# ==== MICROSOFT GRAPH (app-only, client credentials) ====
MS_TENANT_ID = os.getenv("MS_TENANT_ID")
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")

# Schránka, ze které se odesílá (musí odpovídat Application Access Policy).
MAIL_SENDER = os.getenv("MAIL_SENDER", "petrasek@spssecb.cz")

# ==== SMTP (např. Gmail) – dočasně, než bude hotová registrace v Entra ID ====
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")  # default = SMTP_USER
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME")

# ==== Provozní přepínače ====
MAIL_ENABLED = os.getenv("MAIL_ENABLED", "true")
MAIL_DRY_RUN = os.getenv("MAIL_DRY_RUN", "false")
# Bezpečnostní brzda: když je vyplněno, veškerá pošta jde jen na tuto adresu.
MAIL_REDIRECT_TO = os.getenv("MAIL_REDIRECT_TO", "")

# ==== LOG ODESLANÝCH E-MAILŮ (messaging.mail_log v agentdb) ====
MAIL_LOG_ENABLED = os.getenv("MAIL_LOG_ENABLED", "true")
MAIL_LOG_BODY = os.getenv("MAIL_LOG_BODY", "false")  # ukládat i tělo e-mailu
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_DB = os.getenv("POSTGRES_DB", "agentdb")
PG_USER = os.getenv("POSTGRES_USER", "agent")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# ==== GENERAL ====
AGENT_PORT = int(os.getenv("AGENT_PORT", 8005))
