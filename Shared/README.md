# ailacore

Sdílený balíček pro všechny AILa služby. Cíl: nová služba si nikdy sama nevymýšlí vlastní DB config ani vlastní auth logiku — obojí je tady.

- `ailacore.db` — jeden asyncpg pool na proces (`get_pool()` / `close_pool()`), čte `POSTGRES_HOST/PORT/USER/PASSWORD/DB` z env (stejné výchozí hodnoty jako `docker-compose.yml`).
- `ailacore.auth` — RFID + heslové SSO nad `auth.users`/`auth.rfid_cards`/`auth.web_sessions`. `get_current_user` je FastAPI dependency pro chráněné routy, `require_role("admin", "staff")` pro routy omezené na roli (hrubá kontrola jedné role).
- `ailacore.rbac` — granulární RBAC: kontrola na úrovni jednotlivých oprávnění (`require_permission(...)`, `user_has_permission(...)`). Viz níže.
- `ailacore.models` — sdílené Pydantic modely (`User`, `RFIDCard`, `Role`, `Permission`).
- `ailacore.pocket` — klient na [Pocket API](https://docs.heypocketai.com/docs/api) (nahrávky/přepisy/AI shrnutí schůzek). Kterýkoli agent tak může tahat přepisy schůzek — jako podklad pro odpověď, nebo jako instrukční materiál pro jiného agenta — bez vlastní httpx logiky. Viz níže.

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

Bez nastaveného `POCKET_API_KEY` každé volání skončí `RuntimeError` hned na
začátku, ne až chybou 401 z Pocket.

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
