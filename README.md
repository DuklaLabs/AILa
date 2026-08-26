# AILa

Multi-agent backend pro DuklaLabs. Sdílené jádro (DB schéma, RFID/heslové SSO, DB pool) je v `Shared/ailacore` — viz `Shared/README.md`. Nová služba vychází z `Template/` (viz `Template/Readme.md`).

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

Ostatní adresáře (`Skladník`, `Nakupcik`, `Dokumentátor`, `Projekták`, `Výroba`, `UI`, `YOLODetector`, `General`, `listener`, `llama`) v compose zapojené nejsou:
- **Skladník** — nejdál rozjetá další služba (sklad, Vlna 1); před zapojením potřebuje přejít z vlastního/rozporného DB configu na `ailacore.db`.
- **Messenger** — nepoužitá kopie `Template/`, bez vlastního obsahu; klidně smazat, až bude potřeba skutečná služba na jejím místě.
- **General** — rozbitý prototyp orchestrátoru (chybějící `app/` balíček, chybějící import). Dává smysl opravit až budou aspoň dvě reálné služby, mezi kterými má orchestrovat.
- Zbytek jsou nedotčené/nerozjeté stuby.
