# ailacore

Sdílený balíček pro všechny AILa služby. Cíl: nová služba si nikdy sama nevymýšlí vlastní DB config ani vlastní auth logiku — obojí je tady.

- `ailacore.db` — jeden asyncpg pool na proces (`get_pool()` / `close_pool()`), čte `POSTGRES_HOST/PORT/USER/PASSWORD/DB` z env (stejné výchozí hodnoty jako `docker-compose.yml`).
- `ailacore.auth` — RFID + heslové SSO nad `auth.users`/`auth.rfid_cards`/`auth.web_sessions`. `get_current_user` je FastAPI dependency pro chráněné routy, `require_role("admin", "staff")` pro routy omezené na roli.
- `ailacore.models` — sdílené Pydantic modely (`User`, `RFIDCard`).

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
