# ailacore

Sdílený balíček pro všechny AILa služby. Cíl: nová služba si nikdy sama nevymýšlí vlastní DB config ani vlastní auth logiku — obojí je tady.

- `ailacore.db` — jeden asyncpg pool na proces (`get_pool()` / `close_pool()`), čte `POSTGRES_HOST/PORT/USER/PASSWORD/DB` z env (stejné výchozí hodnoty jako `docker-compose.yml`).
- `ailacore.auth` — RFID + heslové SSO nad `auth.users`/`auth.rfid_cards`/`auth.web_sessions`. `get_current_user` je FastAPI dependency pro chráněné routy, `require_role("admin", "staff")` pro routy omezené na roli (hrubá kontrola jedné role).
- `ailacore.rbac` — granulární RBAC: kontrola na úrovni jednotlivých oprávnění (`require_permission(...)`, `user_has_permission(...)`). Viz níže.
- `ailacore.models` — sdílené Pydantic modely (`User`, `RFIDCard`, `Role`, `Permission`).
- `ailacore.pocket` — klient na [Pocket API](https://docs.heypocketai.com/docs/api) (nahrávky/přepisy/AI shrnutí schůzek). Kterýkoli agent tak může tahat přepisy schůzek — jako podklad pro odpověď, nebo jako instrukční materiál pro jiného agenta — bez vlastní httpx logiky. Viz níže.
- `ailacore.obsidian` — klient na [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin, pro dlouhodobou paměť agentů jako čitelné/editovatelné markdown poznámky ve vaultu. Viz níže.
- `ailacore.memory` — orchestrace sdílené paměti agentů nad `ailacore.obsidian`: jedna konvence (`Projects/<project>/context.md` + `log.md`, `Knowledge Base/<topic>.md`), aby si agenti mezi sebou mohli číst poznámky, aniž by si každý vymýšlel vlastní strukturu. Viz níže.
- `ailacore.llm` — jedno místo pro volání LLM, routuje na lokální Ollama nebo na 9Router podle toho, jestli požadavek nese citlivá data. Viz níže.

## Použití v nové službě

Dockerfile nové služby musí mít `Shared/` v build kontextu (viz `Template/Dockerfile` jako vzor) a nainstalovat balíček editable:

```
COPY Shared /shared
RUN pip install --no-cache-dir -e /shared
```

V kódu služby:

```python
from fastapi import Depends, FastAPI
from ailacore.db import get_pool, close_pool
from ailacore.auth import get_current_user, require_role
from ailacore.models import User

app = FastAPI()

@app.on_event("shutdown")
async def _shutdown():
    await close_pool()

@app.get("/api/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return user

@app.delete("/api/something/{id}", dependencies=[Depends(require_role("admin"))])
async def delete_something(id: int):
    pool = await get_pool()
    ...
```

Žádná služba by neměla mít vlastní `DB_CONFIG` dict ani vlastní `require_login`/cookie kontrolu — obojí nahrazuje tento balíček.

## Pocket (`ailacore.pocket`)

Klient nad veřejným Pocket API (nahrávky schůzek, přepisy, AI shrnutí).
Vyžaduje v env proměnnou `POCKET_API_KEY` (org API klíč `pk_xxx` z nastavení
Pocket organizace); `POCKET_BASE_URL` má rozumný default a měnit se nemusí.

```python
from ailacore.pocket import list_recordings, get_recording, search_recordings

recordings = await list_recordings(limit=10)
detail = await get_recording(recordings["data"][0]["id"])  # včetně transcript + summary
hits = await search_recordings("rozpočet na příští čtvrtletí")
```

Nahrání nové nahrávky (`create_upload_url` + `upload_audio`) potřebuje navíc
`POCKET_UPLOAD_API_KEY` — Pocket na `/recordings/upload-url` vrací 403 pro
org klíč ("insufficient scope"), vyžaduje osobní klíč se scope
`recordings:write` (viz Pocket nastavení → API klíče). Bez toho `create_upload_url`
padne s `RuntimeError` hned, ne až 403 z Pocket.

Bez nastaveného `POCKET_API_KEY` každé volání skončí `RuntimeError` hned na
začátku, ne až chybou 401 z Pocket.

## Obsidian (`ailacore.obsidian`)

Klient nad pluginem [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api)
pro Obsidian. Slouží jako paměť pro agenty: cokoliv, co si agent potřebuje
zapamatovat napříč běhy a co má být zároveň čitelné/editovatelné člověkem,
jde sem místo do DB nebo do lokálního souboru — výsledkem je normální
markdown poznámka ve vaultu, kterou kdokoliv otevře v Obsidianu.

Tohle je záměrně jen tenký HTTP klient bez názoru na strukturu vaultu —
pro sdílenou paměť **mezi agenty** (kde na struktuře/cestách záleží, aby si
dva agenti nepsali do dvou různých míst) používej `ailacore.memory` níže
místo přímého volání tohoto modulu.

Vyžaduje běžící Obsidian s otevřeným vaultem a nainstalovaným pluginem
Local REST API (nastavení pluginu → API key). Endpoint je jen loopback
(`https://127.0.0.1:27124` ve výchozím stavu, self-signed cert — proto klient
volá s `verify=False`), takže tohle funguje jen na stroji, kde Obsidian
skutečně běží — ne jako sdílená služba pro víc strojů.

```python
from ailacore.obsidian import (
    get_note, create_or_update_note, append_to_note,
    patch_note, list_notes, search_notes, delete_note,
)

await create_or_update_note("Agents/Projekťák/2026-09-15.md", "# Shrnutí\n...")
await append_to_note("Agents/Projekťák/log.md", "\n- nový poznatek")
content = await get_note("Agents/Projekťák/2026-09-15.md")
notes = await list_notes("Agents/Projekťák")
hits = await search_notes("rozpočet")
```

Env proměnné: `OBSIDIAN_API_KEY` (povinné pro vše kromě `get_status()`),
`OBSIDIAN_BASE_URL` (default `https://127.0.0.1:27124`, měnit jen když
Obsidian běží jinde než na localhostu nebo na jiném portu).

**V Dockeru:** Obsidian sám v kontejneru neběží (je to desktopová appka) —
běží na hostitelském stroji, kontejner na něj musí dosáhnout přes
`host.docker.internal` místo `127.0.0.1`. Vzor je v `docker-compose.yml` u
`projects-server`: `OBSIDIAN_BASE_URL=https://host.docker.internal:27124` +
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```
(`extra_hosts` řádek je potřeba jen na Linuxu — Docker Desktop na
Windows/macOS `host.docker.internal` resolvuje sám). Pro jakoukoli další
službu, co bude `ailacore.obsidian` (nebo `ailacore.memory`) používat, stačí
okopírovat obojí.

## Orchestrace paměti (`ailacore.memory`)

Sdílená paměť agentů nad `ailacore.obsidian` — řeší otázku *kam přesně* se
co ukládá, aby agenti napříč službami (Pocket task translator, General
orchestrátor, ...) psali a četli ze stejného místa, ne každý do vlastní
struktury:

- `Projects/<project>/context.md` — jeden živý souhrn na projekt, dělený na
  sekce (`## Fakta`, `## Rozhodnutí`, ...), doplňovaný po sekcích místo
  přepisu celé poznámky.
- `Projects/<project>/log.md` — append-only časovaný deník toho, co který
  agent udělal/rozhodl — sdílený "co se stalo" feed napříč agenty.
- `Knowledge Base/<topic>.md` — věci, co přestaly být vázané na jeden
  projekt. Píše se sem výhradně přes `promote()`, nikdy automaticky.

`project` je slug, na kterém se agenti musí shodnout (typicky id/slug
projektu z `Projects` služby) — není to volný text.

```python
from ailacore.memory import remember, log, recall, recent_log, search, promote

await remember("kroky-uvolneni", "Rozhodnutí", "Termín posunut na pátek")
await log("kroky-uvolneni", "Task translator vytvořil 3 úkoly ze schůzky")

context = await recall("kroky-uvolneni")       # celá context.md
timeline = await recent_log("kroky-uvolneni")  # posledních 20 řádků logu
hits = await search("rozpočet", project="kroky-uvolneni")  # jen v rámci projektu

# když se poznatek přestane týkat jen jednoho projektu:
await promote("kroky-uvolneni", "RBAC kontrola je vždy na úrovni permission, ne role", "rbac")
```

`remember()` si poradí, i když poznámka nebo sekce ještě neexistuje — první
volání pro daný projekt/sekci ji založí, další jen doplňují (`PATCH` pod
heading; když heading/poznámka chybí, spadne na vytvoření/append). Platí
pro to stejné env proměnné a Docker poznámky jako pro `ailacore.obsidian`
výše (`OBSIDIAN_API_KEY`, `OBSIDIAN_BASE_URL`, `host.docker.internal`).

## LLM routing (`ailacore.llm`)

Jedno místo, kudy jde libovolné volání LLM, ať ho potřebuje kterýkoli agent.
Rozhoduje se podle jediného explicitního parametru `sensitive` — žádný
default, protože špatný odhad na obě strany bolí jinak (odhad "citlivé" jen
zbytečně nevyužije levnější model, odhad "necitlivé" může poslat PII/interní
data ven k cloudovému provideru):

- `sensitive=True` → lokální Ollama (`docker-compose.yml` služba `ollama`) —
  nic neopustí naši síť. Použij pro cokoli s reálnými lidmi (jména, e-maily,
  obsah schůzek, DB výstupy) nebo kdykoli si nejsi jistý.
- `sensitive=False` → [9Router](https://9router.com) (`docker-compose.yml`
  služba `router`, image `decolua/9router`) — self-hosted OpenAI-kompatibilní
  router před 40+ cloud/subscription/free providery. Použij pro požadavky bez
  citlivého obsahu, kde se vyplatí větší/levnější/free model, než jaký běží
  lokálně.

```python
from ailacore.llm import complete

# citlivé — jde na lokální Ollama
reply = await complete("Shrň tento přepis schůzky...", sensitive=True)

# necitlivé — jde přes 9Router na model zvolený v ROUTER_MODEL / explicitně
reply = await complete(
    "Přelož tuhle veřejnou dokumentaci do angličtiny...",
    sensitive=False,
    model="kr/claude-sonnet-4.5",
)
```

Env proměnné: `OLLAMA_URL` (default `http://ollama:11434`), `OLLAMA_MODEL`
(default `qwen2.5:14b`) — stejné jako u ostatních přímých volání Ollamy v repu
— a pro 9Router `ROUTER_URL` (default `http://router:20128/v1`),
`ROUTER_API_KEY`, `ROUTER_MODEL`. `ROUTER_API_KEY` je klíč vygenerovaný v
9Router dashboardu (`http://localhost:20128` → Providers/Endpoint), ne
sdílený se žádnou jinou službou — tam se také zakládají a spravují samotní
provideři/modely, ne přes env. Bez `ROUTER_API_KEY` (nebo bez modelu — ani v
parametru, ani v `ROUTER_MODEL`) `complete(..., sensitive=False)` spadne s
`RuntimeError` hned, ne až chybou z 9Router.

Zatím nic v repu `sensitive=False` nevolá — obě dnešní reálná volání LLM
(`Security_agent`, Pocket task extraction v `Projects`) běží s citlivými daty
(PII studentů / obsah schůzek), takže zůstávají na Ollamě. `ailacore.llm` je
tu připravený pro další use-case, který se rozhodneme takhle směrovat.

## RBAC (granular)

Tři katalogové tabulky ve schématu `auth` (migrace `0014_rbac`):

- `auth.roles` — katalog rolí (`admin`, `staff`, `member`, `student`, `public` jsou systémové).
- `auth.permissions` — katalog oprávnění. Název je `schema.resource:action`, např. `internal.open_hours:write`, `orders.order:approve`.
- `auth.role_permissions` — které oprávnění dává která role.

Přiřazení uživateli:

- `auth.users.role` — **primární** role (jedna, beze změny oproti dřívějšku).
- `auth.user_roles` — libovolný počet **sekundárních** rolí navíc.
- `auth.user_permissions` — přímé per-user granty (obejdou role).

Efektivní oprávnění = sjednocení všech tří zdrojů. Wildcard je povolený jen
v *přidělené* množině: `*` pokryje vše (drží ho `admin`), `inventory.*` pokryje
`inventory.item:read` i `inventory.stock:adjust`. Požadované oprávnění je vždy
konkrétní řetězec.

```python
from fastapi import Depends
from ailacore.rbac import require_permission, user_has_permission

# routa vyžaduje oprávnění (admin přes '*' projde vždy)
@app.get("/api/orders", dependencies=[Depends(require_permission("orders.order:read"))])
async def list_orders(): ...

# víc oprávnění: mode="all" (výchozí) / "any"
@app.post("/api/orders", dependencies=[Depends(require_permission("orders.order:create"))])
async def create_order(): ...

# imperativní kontrola uvnitř handleru
async def handler(user = Depends(get_current_user)):
    if await user_has_permission(user, "orders.order:approve"):
        ...
```

Výsledek se drží v procesní TTL cache — `RBAC_CACHE_TTL` (výchozí `30` s, `0` vypíná).
Po změně grantů volej `ailacore.rbac.clear_permission_cache(user_id)`, jinak se
změna projeví až po vypršení TTL.

**Přidání nového oprávnění** = migrace, která ho vloží do `auth.permissions`
a namapuje ho v `auth.role_permissions`:

```python
op.execute("INSERT INTO auth.permissions (name, description) VALUES "
           "('maintenance.task:close', 'Uzavřít servisní úkol');")
op.execute("INSERT INTO auth.role_permissions (role_name, permission_name) VALUES "
           "('staff', 'maintenance.task:close');")
```

## RBAC admin UI (`ailacore.admin`)

Sdílená správa RBAC — JSON API + React konzole, kterou si služba připojí dvěma řádky:

```python
import os
from ailacore.admin import rbac_api_router, mount_admin_ui

app.include_router(rbac_api_router)                       # /api/rbac/... (JSON)
mount_admin_ui(app, os.getenv("RBAC_UI_DIST", "rbac-ui-dist"))  # /admin/rbac/ (SPA)
```

- **API** pod `/api/rbac`: `permissions` (katalog), `roles` + `roles/{n}/permissions`,
  `users` + `users/{id}/roles` + `users/{id}/permissions`, `audit`, `effective`.
  Guardy přes `require_permission` — `auth.role:manage` / `auth.user:read|write` /
  `auth.permission:grant` (z katalogu `0014`; `staff` je defaultně nemá → konzole je jen pro adminy).
- Každá mutace jde v jedné transakci se zápisem do `auth.audit_log` (migrace `0015`,
  přes `ailacore.audit.record_audit`) a invaliduje `rbac` cache.
- **SPA** je React appka z `UI/` (Vite, `base=/admin/rbac/`). Servíruje se přes
  `mount_admin_ui` na **stejném originu** jako API (kvůli cookie session `dl_session`).
  Dockerfile služby musí `UI/` buildnout a `dist` nakopírovat tam, kam ukazuje
  `RBAC_UI_DIST` — vzor je stage `rbac-ui` v `AccessRequest/Dockerfile`.
- Když build chybí (dev `pip install -e` bez `npm run build`), `mount_admin_ui` jen
  zaloguje varování a API běží dál.
