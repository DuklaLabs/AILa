# Template

Výchozí bod pro novou AILa službu. Obsahuje:

- `app/main.py` — FastAPI app, `/healthz`, úklid sdíleného DB poolu při shutdownu.
  Zakomentovaný vzor pro volitelné zamountování sdílené RBAC administrace
  (`ailacore.admin.rbac_api_router` + `mount_admin_ui`, `/admin/rbac/`) — viz
  `Shared/README.md`, sekce „RBAC admin UI".
- `app/router.py` — `POST /task` (deleguje na `app.agent.process_task`), vzor
  chráněné routy dostupné komukoli přihlášenému (`GET /whoami`), routy
  omezené hrubě na roli (`GET /admin-only`, `require_role`) a routy omezené
  na konkrétní RBAC oprávnění (`GET /reservations`, `require_permission` —
  preferovaný vzor pro nový kód, viz `Shared/README.md` sekce RBAC).
- `app/agent.py` — vzor přístupu do sdílené Postgres přes `ailacore.db.get_pool()`.
- `app/models.py`, `app/utils.py` — prázdné, čekají na obsah nové služby.
- `Dockerfile` — počítá s tím, že build context je kořen repa (kvůli
  `Shared/`), instaluje `-e /shared` a pak `Template/requirements.txt` +
  `COPY Template/ .` — obě cesty se musí přejmenovat na adresář nové služby
  (krok 1 níže). `--trusted-host pypi.org …` je obchvat MITM certifikátů na
  školních/firemních sítích, ne bezpečnostní díra k řešení.

## Jak založit novou službu z tohoto vzoru

1. Zkopíruj `Template/` do `<NováSlužba>/`, přejmenuj `title=` v `main.py`
   a v `<NováSlužba>/Dockerfile` přepiš oba výskyty `Template/` (řádky
   `COPY Template/requirements.txt .` a `COPY Template/ .`) na
   `<NováSlužba>/` — jinak build selže (soubor pod starou cestou neexistuje).
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
5. Potřebuje-li služba nový katalog RBAC oprávnění, přidej je vlastní migrací
   (insert do `auth.permissions` + `auth.role_permissions`, vzor v
   `Database/migrations/versions/0014_rbac.py` a v `Shared/README.md`).
