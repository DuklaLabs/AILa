# Nakupcik

Prototyp „nákupčí" agenta volaného `General/orchestrator.py`
(`PROCUREMENT_URL = "http://nakupcik:8002"`). Není v `docker-compose.yml`,
nepoužívá `ailacore`. **V aktuálním stavu nenaběhne.**

## Momentálně rozbité

- `app/session.py` je **prázdný soubor** (0 bajtů). `app/main.py` dělá
  `from app.session import async_session, engine` — `ImportError` hned při startu.
- FastAPI titul appky je `"Inventory Agent (Skladník)"` (zkopírováno ze
  `Skladník`), ne nákupní logika — obsah `app/main.py` je prakticky identická
  kopie skladového CRUD nad materiály (`/materials`, `/materials/{id}/add`,
  `/materials/{id}/remove`, `/materials/low`), žádná vlastní logika objednávek
  (vytváření objednávky z nedostatkových položek, komunikace s dodavatelem apod.
  tu chybí úplně, na rozdíl od `Skladník/app/services/order_service.py`, který
  aspoň koncept `create_order_for_low_stock` má, byť taky rozbitý).
- `app/models.py` (Base/Material/MaterialMovement, SQLAlchemy) je v pořádku sám
  o sobě, jen na něj `main.py` nedosáhne kvůli výše uvedenému importu.

Než se v tomhle pokračuje: buď doplnit `app/session.py` (engine + async_session,
analogicky `Skladník/app/db/session.py`) a napsat skutečnou nákupní logiku
(namísto kopie skladového CRUD), nebo modul smazat a nechat `General`
komunikovat jen se `Skladník`, dokud nákupčí nemá důvod na existenci navíc.

## Dockerfile

`EXPOSE 8200`, `CMD uvicorn app.main:app --port 8002` — stejný nesoulad
EXPOSE/skutečný port jako u `Skladník` (neškodné, jen matoucí).

## Spuštění (po doplnění `app/session.py`)

```
cd Nakupcik
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```
