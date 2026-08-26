# Template

Výchozí bod pro novou AILa službu. Obsahuje:

- `app/main.py` — FastAPI app, `/healthz`, úklid sdíleného DB poolu při shutdownu.
- `app/router.py` — vzor chráněné routy (`/whoami`, kdokoliv přihlášený) a routy omezené rolí (`/admin-only`).
- `app/agent.py` — vzor přístupu do sdílené Postgres přes `ailacore.db.get_pool()`.
- `Dockerfile` — počítá s tím, že build context je kořen repa (kvůli `Shared/`).

## Jak založit novou službu z tohoto vzoru

1. Zkopíruj `Template/` do `<NováSlužba>/`, přejmenuj `title=` v `main.py`.
2. V `docker-compose.yml` přidej službu:
   ```yaml
   nova-sluzba:
     build:
       context: .
       dockerfile: NováSlužba/Dockerfile
     ports:
       - "PORT:PORT"
     networks:
       - agentnet
     depends_on:
       - postgres
     environment:
       POSTGRES_DB: agentdb
       POSTGRES_USER: agent
       POSTGRES_PASSWORD: agentpass
       POSTGRES_HOST: postgres
   ```
3. Nepiš vlastní `DB_CONFIG` dict ani vlastní cookie/login kontrolu — obojí je v `Shared/ailacore` (viz `Shared/README.md`).
4. Nová schema změna → migrace v `Database/migrations/`, ne ruční SQL.
