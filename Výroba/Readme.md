# Výroba

Nerozjetý stub, není napojený do `docker-compose.yml` (viz kořenové
`README.md`, sekce „Stav služeb"). Neexistuje žádná specifikace toho, co má
agent dělat – jen holý FastAPI skeleton, byte-identický s `Dokumentátor/`
(stejný `app/main.py`, `router.py`, `agent.py`, `Dockerfile`,
`requirements.txt`), bez napojení na `ailacore` (žádná DB, žádné SSO/RBAC).

## Aktuální stav kódu

- `app/main.py` – `FastAPI(title="Název agenta")` (nepřejmenováno), mountuje
  jediný router.
- `app/router.py` – `POST /task`, přijme libovolný `dict` a předá ho
  `app.agent.process_task`.
- `app/agent.py` – `process_task` je no-op: vrátí vždy
  `{"status": "ok", "message": "Zpracováno"}`, bez ohledu na vstup.
- `app/models.py`, `app/utils.py` – prázdné soubory.
- `requirements.txt` – jen `fastapi`, `uvicorn`, `requests` (žádné `ailacore`,
  žádné DB knihovny).
- `Dockerfile` – generický, bez `Shared/` v build kontextu → `ailacore` by
  bez úpravy nešel importovat, ani kdyby ho kód používal.

## Než se stane skutečnou službou

Vychází z `Template/` (viz `Template/Readme.md`), ne z tohoto stavu – nová
implementace (výrobní/dílenské procesy DuklaLabs) by měla začít znovu podle
šablony (DB pool, SSO, RBAC, `Shared/` v Dockerfile build kontextu), tenhle
kód nic z toho nemá.
