# Projekták

Nedotčený stub, byte-identický s `Dokumentátor/` (stejný `app/main.py`,
`router.py`, `agent.py`, `Dockerfile`, `requirements.txt`). Není v
`docker-compose.yml` ani zmíněný v kořenovém `README.md` – zjevně starý,
nikam nedotažený prototyp z rané fáze repa (jediný commit v historii),
předcházející dnešní projektový systém v `Projects/` (port 8006, viz
`Projects/README.md`), který jeho funkci fakticky nahradil.

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
  bez úpravy nešel importovat.

Pro cokoli, co má tenhle adresář dělat, dává smysl začít znovu z `Template/`
(viz `Template/Readme.md`) – nebo ověřit, jestli zamýšlenou funkci už
nepokrývá `Projects/`.
