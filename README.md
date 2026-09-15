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

Ostatní adresáře (`Skladník`, `Nakupcik`, `Dokumentátor`, `Výroba`, `UI`, `YOLODetector`, `General`, `listener`, `llama`, `PocketPlayground`) samostatnou službou v compose nejsou:
- **UI** — React SPA: sdílená RBAC admin konzole (`ailacore.admin`, `/admin/rbac/`) a projektová appka (`/app/projects/`). Nemá vlastní kontejner; jednotlivé buildy (`npm run build`, `npm run build:projects`) si nakopíruje do image služba, která je hostí (viz `AccessRequest/Dockerfile` stage `rbac-ui`, `Projects/Dockerfile` stage `projects-ui`). Viz `UI/README.md`.
- **PocketPlayground** — lokální testovací hřiště nad `ailacore.pocket` (Swagger UI + skripty na přepis/extrakci úkolů ze schůzek); nic se z něj nedeployuje. Viz `PocketPlayground/README.md`.
- **Skladník** — nejdál rozjetá další služba (sklad, Vlna 1), ale v repu má dvě neslučitelné DB vrstvy (SQLite vs. Postgres) a rozbitý import v `app/main.py` (nenaběhne beze změny); před zapojením potřebuje přejít z vlastního/rozporného DB configu na `ailacore.db`. Viz `Skladník/README.md`.
- **Nakupcik** — prototyp nákupčího volaný `General`; `app/session.py` je prázdný soubor, takže dnes nenaběhne vůbec. Viz `Nakupcik/README.md`.
- **General** — rozbitý prototyp orchestrátoru (chybějící `app/` balíček, chybějící import). Dává smysl opravit až budou aspoň dvě reálné a funkční služby, mezi kterými má orchestrovat — dnes nefunguje ani `Skladník`, ani `Nakupcik`.
- Zbytek (`Dokumentátor`, `Výroba`, `YOLODetector`, `listener`, `llama`) jsou nedotčené/nerozjeté stuby nebo (YOLODetector, listener) samostatné nástroje mimo hlavní stack — každý má vlastní README/Readme s detaily.

`data/` a `Nová složka/` v kořeni repa nepatří k žádnému z výše popsaných modulů
(nejsou v žádném `docker-compose.yml` build kontextu ani importu) — `data/`
navíc obsahuje mj. i sledované privátní klíče, viz POZOR níže.

## POZOR – sledované tajemství v `data/`

`data/secrets.json` (a `data/cert.pem`) jsou v gitu (`git ls-files data/`
je potvrzuje jako trackované, nejsou v `.gitignore`) a obsahují reálný
VAPID privátní klíč a EC SSL privátní klíč nesouvisející s kódem v tomto
repu (podle `data/config.json` jde o stav nějaké externí kamerové/push
služby, ne o AILa). Než se s tím dál pracuje: klíče rotovat/zneplatnit,
`data/` přidat do `.gitignore` a odebrat z gitu (`git rm --cached`), historie
řešit až po dohodě s vlastníkem repa (force-push/rewrite historie je
destruktivní zásah).
