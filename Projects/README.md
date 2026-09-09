# Projects

Projektový systém DuklaLabs pro prototypový vývoj HW (databanka §5). Postavený
na `ailacore` (DB pool, RFID/heslové SSO, granulární RBAC, audit log), React SPA
je druhý build v `UI/`.

Port **8006**. Schéma `projects` (migrace `Database/migrations/versions/0016_projects.py`).

## Co umí (Milník 1 / MVP)

- **Hierarchie:** workspace → složka (Komerční prototypy / Interní R&D / Globální
  přehledy) → projekt → 5 fází → úkol. Nový projekt se zakládá ze standardizované
  šablony (`projects.phase_templates`), fáze se nakopírují automaticky.
- **Datová karta úkolu:** 1 hlavní řešitel + volitelní spolupracovníci, 5stavový
  semafor (K řešení / V řešení / Interní revize / Blokováno / Hotovo), timeline
  od–do, štítek verze prototypu, odhad hodin, finanční pole (typ nákladu,
  předpokládaná / skutečná cena, stav objednávky).
- **Kanban:** sloupce podle stavu (semafor) v rámci fáze; přetahování karet mezi
  sloupci mění stav (optimisticky). Responzivní – na mobilu se postranní panel
  sklápí a stav úkolu jde měnit i výběrem na kartě. Výběr řešitele /
  spolupracovníků / závislostí je přes rozbalovací seznamy se jmény (endpoint
  `GET /api/users`), ne přes ID.
- **Vzhled:** „glass" karty s rozostřeným pozadím; karty úkolů přebírají barvu
  podle sloupce-stavu, chrome (panel, hlavička, záložky fází) přebírá barvu podle
  kategorie projektu (složky – `folder_kind` z API: Komerční prototypy / Interní
  R&D / Globální přehledy). Animace respektují `prefers-reduced-motion`.
- **Time tracking:** nativní stopky Start/Stop (max jedny běžící na uživatele) +
  ruční zápis minut.
- **Finanční součet projektu:** `Σ skutečných cen + odpracované hodiny × interní
  hodinová sazba` (skrytá, `projects.settings.hourly_rate_czk`, default 500),
  včetně % čerpání rozpočtu. Endpoint `GET /api/projects/{id}/costs`.
- **Návrhy změn od AI:** nevratné / citlivé operace přes MCP nevytvoří přímou
  mutaci, ale `projects.proposals` (pending); člověk s `projects.proposal:review`
  je v SPA schválí/zamítne.

Milníky 2–4 (automatizace, manažerské dashboardy, GitHub) zatím nejsou.

## Endpointy

- `GET /healthz`, `GET /` rozcestník, `GET /login` + `POST /login-check` +
  `POST /login/rfid` + `GET /logout`, `GET /api/me` (identita + oprávnění).
- REST pod `/api`: `users`, `workspaces`, `folders`, `projects` (+`/phases`,
  `/costs`), `phases/{id}/tasks`, `tasks` (+`/status`, `/assignee`,
  `/collaborators`, `/dependencies`), `tasks/{id}/time` (+`/start`, `/manual`),
  `time/stop`, `time/running`, `proposals` (+`/approve`, `/reject`).
- SPA na `/app/projects/` (za přihlášením).
- MCP server na `/mcp` (viz níže).

## RBAC

Katalog `projects.*` + mapování na role seeduje migrace 0016:

| oprávnění | admin | staff | member |
|---|:-:|:-:|:-:|
| `projects.project:read` / `projects.task:read` | ✔ | ✔ | ✔ |
| `projects.task:write` | ✔ | ✔ | ✔ |
| `projects.time:log` / `projects.ai:use` | ✔ | ✔ | ✔ |
| `projects.project:write` / `projects.task:assign` | ✔ | ✔ | — |
| `projects.finance:read` / `projects.finance:write` | ✔ | ✔ | — |
| `projects.time:read_all` / `projects.dashboard:read` | ✔ | ✔ | — |
| `projects.proposal:review` | ✔ | ✔ | — |

Guardy jsou v servisní vrstvě (`app/services/`), ne v routách – REST i MCP jedou
přes stejné funkce `fn(user, ...)`.

## MCP server (napojení AI)

HTTP (streamable) transport na `http://<host>:8006/mcp`. Klient (Claude i vlastní
agent) se autentizuje hlavičkou `Authorization: Bearer <token>`, kde token je
session token z `auth.web_sessions` (stejný jako cookie `dl_session` po
přihlášení). Nástroj bez platného tokenu nebo bez `projects.ai:use` nic neudělá.

- **čtení:** `list_projects`, `get_project`, `list_folders`, `list_tasks`,
  `get_task`, `get_project_costs`, `list_my_time`, `list_proposals`
- **přímý zápis (pod RBAC uživatele):** `create_task`, `update_task_fields`,
  `set_task_status`, `set_task_assignee`, `add_time_entry`
- **jen jako návrh ke schválení:** `propose_change(kind, target_type, target_id,
  payload, summary)` pro `task.delete`, `project.update`, `finance.update`,
  `project.lifecycle` – vznikne `projects.proposals` (pending), skutečná změna
  proběhne až po schválení člověkem v SPA.

Každý zápis přes MCP jde do `auth.audit_log` (`origin: "mcp"`).
Vypnutí: `MCP_ENABLED=false`. Když není nainstalovaný balíček `mcp`, služba
naběhne bez MCP (REST + SPA fungují dál).

## Vývoj

```
# DB (jednou)
cd Database && POSTGRES_HOST=localhost alembic upgrade head

# API
cd Projects && pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8006

# SPA (dev proxy na :8006)
cd UI && npm run dev:projects

# testy
cd Projects && pytest
```
