# Skladník

Prototyp skladového systému (materiály, dodavatelé, objednávky). **Nejrozjetější
z nezapojených služeb** (viz kořenový `README.md`), ale ve zdrojáku je rozpor
mezi dvěma nedokončenými verzemi téhož modulu — než se pokračuje dál, je potřeba
se rozhodnout, která vrstva zůstává, a rozbité importy dopsat/smazat. Nic z
tohoto adresáře není v `docker-compose.yml` a nepoužívá `ailacore`.

## Dvě neslučitelné DB konfigurace

- `app/session.py` (kořen `app/`) — SQLite, `sqlite+aiosqlite:///./procurement.db`,
  natvrdo.
- `app/db/session.py` — `create_async_engine(DATABASE_URL)`, kde `DATABASE_URL`
  (z `app/config.py`) čte env, default
  `postgresql+asyncpg://postgres:postgres@localhost:5432/procurement`.

`app/main.py` importuje z `app.session` (SQLite). `app/api/*` a `app/services/*`
importují z `app.db.session`/`app.db.models` (Postgres). Nikdy neběží obě větve
současně smysluplně nad stejnou databází. Přechod na `ailacore.db` (sdílený pool,
schéma v `Database/migrations/`) zruší obě a nahradí je jednou konzistentní
vrstvou — to je i to, co k tomu píše kořenový README.

## Co skutečně běží: `app/main.py`

Jediný modul, který je zapojený do `app = FastAPI(...)` a spustí se
(`uvicorn app.main:app`). Vlastní inline endpointy nad `app/models.py`
(pozor: **ne** `app/db/models.py`, ale modul `app.models`, který ve
skutečnosti v repu **neexistuje** — `main.py` importuje `Base, Material`
z `app.models`, existuje jen `app/db/models.py`). **Import v `main.py`
tedy padá hned při startu** (`ModuleNotFoundError`), stejně jako chybí import
`Order`/`OrderItem` použitých dál v souboru. Než tohle poběží, je potřeba
opravit importy na `app.db.models` a doplnit `Order`/`OrderItem`.

Zamýšlené endpointy (`app/main.py`): `POST/GET /materials`, `GET /materials/low`,
`POST /orders`, `POST /orders/{id}/item`, `GET /orders`.

## Co je v repu, ale nikam nenapojené a samo o sobě nefunkční

- `app/api/materials.py`, `app/api/orders.py`, `app/api/suppliers.py` — žádný
  router není `include_router`ovaný v `main.py`. `materials.py` navíc
  nemá `import select`; `suppliers.py` importuje `..db.session.get_db` a
  `..db.repositories.suppliers_repo`, ani jedno v repu neexistuje.
- `app/services/material_service.py`, `app/services/order_service.py` — importují
  `app.db.repositories.*_repo`, které v repu nejsou (žádný `app/db/repositories/`
  adresář existuje).

## Datový model (`app/db/models.py`, míří na Postgres schéma `procurement`)

`Material` (name, category, stock, min_stock, unit, supplier_id) →
`Supplier` (name, contact, website) ; `Order` (status enum draft/created/sent/
received/canceled) → `OrderItem` (order_id, material_id, quantity).

## Dockerfile nesedí s app.main

`EXPOSE 8100`, ale `CMD` spouští `uvicorn app.main:app --port 8001`. Port 8100
v `EXPOSE` je jen dokumentační metadata (nic neblokuje), ale je matoucí —
skutečný poslouchací port je **8001** (na to se odkazuje i `General/orchestrator.py`
přes `INVENTORY_URL = "http://skladnik:8001"`).

## Spuštění (po opravě importu v `main.py`)

```
cd Skladník
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```
