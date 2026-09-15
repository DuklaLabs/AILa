# listener

Samostatný (mimo `docker-compose.yml`) můstek Postgres → webhook. Naslouchá
na Postgres `LISTEN/NOTIFY` kanálu `errors_channel` a každou notifikaci
přepošle jako `POST` na `N8N_WEBHOOK_URL` (n8n nebo jiný webhook endpoint mimo
tento repo). Autoreconnect smyčka — při pádu spojení počká 3 s a zkusí znovu.

`listener.py` čte env `POSTGRES_DB/USER/PASSWORD/HOST` a `N8N_WEBHOOK_URL`
(žádné defaulty — bez nich spadne na `psycopg2.connect`/prázdné URL).

Odpovídající `NOTIFY errors_channel, '<json>'` musí posílat něco jiného
(např. DB trigger) — v tomto repu žádný takový trigger/migrace není, takže
tenhle listener dnes nemá co poslouchat, dokud producent notifikace nevznikne.

```
cd listener
pip install -r requirements.txt
POSTGRES_DB=agentdb POSTGRES_USER=agent POSTGRES_PASSWORD=agentpass \
  POSTGRES_HOST=localhost N8N_WEBHOOK_URL=https://... python listener.py
```
