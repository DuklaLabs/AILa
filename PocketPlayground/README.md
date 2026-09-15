# PocketPlayground

Lokální testovací hřiště nad `ailacore.pocket` (viz `Shared/README.md`, sekce
„Pocket"). **Není AILa služba**, nic tu neběží v `docker-compose.yml`, nic se
nedeployuje. Slouží k ručnímu ladění Pocket API a k jednorázovým skriptům, než
funkčnost přejde do skutečné služby (viz `Projects/app/services/pocket_bridge.py`
pro produkční verzi Pocket panelu).

Každý soubor má vlastní docstring popisující účel a spuštění — tohle je jen
přehled napříč nimi.

## Soubory

- **`main.py`** — FastAPI appka se Swagger UI nad `ailacore.pocket`:
  `GET /healthz`, `GET /recordings`, `GET /recordings/{id}`, `POST /search`,
  `GET /tags`, `POST /recordings/upload`. Spustit lokálně
  (`uvicorn PocketPlayground.main:app --reload --port 8099`) a klikat v
  `/docs`, bez potřeby cokoliv jiného rozjíždět.
- **`latest_transcript.py`** — jednorázový skript: vytáhne poslední přepsanou
  (`state == "completed"`) nahrávku z Pocket a vypíše přepis do konzole
  (speaker: text po řádcích).
- **`task_translator.py`** — celá pipeline „schůzka → návrh úkolu v Projects":
  poslední přepsaná nahrávka → lokální Ollama extrahuje kandidátní úkoly (název,
  popis, odhad řešitele/projektu/fáze) → fuzzy shoda (`difflib.SequenceMatcher`)
  proti reálným projektům/fázím/uživatelům z běžící `Projects` služby →
  `propose_change("task.create", ...)` přes MCP (`Projects/mcp`). Nic nezapisuje
  přímo — každý kandidát skončí jako `projects.proposals` (pending), schvaluje
  člověk v UI Projects („Návrhy změn od AI"). Toto je referenční/testovací
  implementace téhož, co dělá `Projects` Pocket panel v produkci.

## Konfigurace

Zkopírovat `.env.example` → `.env`:

- `POCKET_API_KEY` (org klíč, čtení nahrávek/přepisů — používá `main.py` i
  `latest_transcript.py`), `POCKET_UPLOAD_API_KEY` (osobní klíč se scope
  `recordings:write`, jen pro `POST /recordings/upload` v `main.py`).
- `PROJECTS_BASE_URL`, `AI_AGENT_USERNAME`/`AI_AGENT_PASSWORD` (účet založený
  přes `Database/seed_ai_agent.py`), `OLLAMA_URL`/`OLLAMA_MODEL` — jen pro
  `task_translator.py`.

## Spuštění

```
pip install -r PocketPlayground/requirements.txt
pip install -e Shared        # ailacore

uvicorn PocketPlayground.main:app --reload --port 8099   # Swagger UI hřiště
python PocketPlayground/latest_transcript.py             # poslední přepis
python PocketPlayground/task_translator.py               # schůzka -> návrhy úkolů
```
