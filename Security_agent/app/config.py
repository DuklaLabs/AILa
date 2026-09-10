import os

# E-maily se odesílají přes službu Messenger (Microsoft Graph), ne přímo SMTP.
MESSENGER_URL = os.getenv("MESSENGER_URL", "http://messenger:8005")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "postgres"),
    "database": os.getenv("DB_NAME", "agentdb"),
    "user": os.getenv("DB_USER", "agent"),
    "password": os.getenv("DB_PASSWORD", ""),
    "port": int(os.getenv("DB_PORT", 5432))
}

AGENT_PORT = int(os.getenv("AGENT_PORT", 8004))

