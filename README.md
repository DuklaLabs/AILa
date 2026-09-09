# AILa

Multi-agent backend pro DuklaLabs. Sdílené jádro (DB schéma, RFID/heslové SSO, DB pool, granulární RBAC, RBAC admin UI) je v `Shared/ailacore` — viz `Shared/README.md`. Nová služba vychází z `Template/` (viz `Template/Readme.md`).

## Rychlý start

```
docker compose up -d postgres
cd Database
pip install -r requirements.txt
alembic upgrade head
python seed_admin.py <username> <password> [rfid_card_uid]
```

Pak `docker compose up -d` pro zbylé služby.

## Stav služeb

Zapojené v `docker-compose.yml`:
- `postgres`, `ollama`
- `access-request-server` (8003) — docházka na kroužek, otevřené hodiny, rezervace, RFID/heslové přihlášení
- `security-agent` (8004) — LLM agent na týdenní/stavové e-maily (Flask, zatím nepřevedeno na `ailacore`)
- `messenger` (8005) — odesílání pošty přes Microsoft Graph + log do `messaging.mail_log`
- `projects-server` (8006) — projektový systém (hierarchie workspace→složka→projekt→fáze→úkol, datová karta úkolu, kanban, time tracking, finanční součty). React SPA na `/app/projects/`, MCP server pro AI na `/mcp`. Viz `Projects/README.md`.

Ostatní adresáře (`Skladník`, `Nakupcik`, `Dokumentátor`, `Výroba`, `UI`, `YOLODetector`, `General`, `listener`, `llama`) samostatnou službou v compose nejsou:
- **UI** — React SPA: sdílená RBAC admin konzole (`ailacore.admin`, `/admin/rbac/`) a projektová appka (`/app/projects/`). Nemá vlastní kontejner; jednotlivé buildy (`npm run build`, `npm run build:projects`) si nakopíruje do image služba, která je hostí (viz `AccessRequest/Dockerfile` stage `rbac-ui`, `Projects/Dockerfile` stage `projects-ui`). Viz `UI/README.md`.
- **Skladník** — nejdál rozjetá další služba (sklad, Vlna 1); před zapojením potřebuje přejít z vlastního/rozporného DB configu na `ailacore.db`.
- **Messenger** — nepoužitá kopie `Template/`, bez vlastního obsahu; klidně smazat, až bude potřeba skutečná služba na jejím místě.
- **General** — rozbitý prototyp orchestrátoru (chybějící `app/` balíček, chybějící import). Dává smysl opravit až budou aspoň dvě reálné služby, mezi kterými má orchestrovat.
- Zbytek jsou nedotčené/nerozjeté stuby.
