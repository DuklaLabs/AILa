# Security_agent

LLM agent (Ollama, ReAct/tool-calling) pro uvolňování studentů z výuky a týdenní/
stavové e-maily. Port **8004**. Flask, ne FastAPI — a **není** převeden na
`ailacore` (vlastní `DB_CONFIG` dict, vlastní psycopg2 spojení, žádné RFID/RBAC).
Viz kořenový `README.md`, sekce „Stav služeb".

## Architektura

- `app/agent.py` — `OllamaReactAgent`: smyčka nad `ollama.chat(..., tools=...)`
  (max 10 iterací), model `llama3.2:8b-instruct` (natvrdo, ne přes env). Deklaruje
  5 nástrojů (viz níže) a `run_agent(user_message)` jako vstupní bod.
- `app/tools.py` — implementace nástrojů: `db_query`, `send_email`,
  `generate_weekly_report`, `generate_student_status_email`, `process_teacher_reply`.
- `app/config.py` — `MESSENGER_URL` (default `http://messenger:8005`),
  `DB_CONFIG` (host/db/user/password/port z env), `AGENT_PORT` (8004).
- `app/run_agent_service.py` — **skutečný entrypoint** (viz `Dockerfile` CMD):
  Flask server (`POST /run`) + `scheduler.py` spuštěný ve vlastním threadu.
- `app/agent_server.py` — starší/alternativní Flask entrypoint bez scheduleru
  (`POST /run` samostatně). Dockerfile ho nepoužívá — spíš pozůstatek, neudržovat
  duplicitně s `run_agent_service.py`.
- `app/scheduler.py` — APScheduler joby: čtvrtek 12:00 týdenní report učitelům,
  pátek 12:00 stavový e-mail studentům.

## Známé rozbité věci (než se do toho šahá dál)

- **`scheduler.py` má rozbité volání**: `add_job` registruje `send_teacher_reports`
  a `send_student_updates`, ale v souboru jsou definované funkce
  `teacher_weekly_job` a `student_status_job`. Joby tedy při spuštění spadnou na
  `NameError`. Oprava = přejmenovat volání na skutečné názvy funkcí.
- **`tools.db_query` spouští syrové SQL od LLM bez jakéhokoli omezení** (žádný
  read-only guard, žádný whitelist tabulek) přímo přes `psycopg2` s `conn.commit()`.
  Model si sám skládá dotazy nad `internal.students` / `internal.excused` (viz
  `process_teacher_reply`). Netriviální bezpečnostní riziko, pokud se agent někdy
  vystaví míň důvěryhodnému vstupu než internímu promptu.
- Žádná autentizace/autorizace na `POST /run` — kdokoli s přístupem na port 8004
  může spustit uvolnění libovolného studenta.

## Nástroje agenta

| Nástroj | Co dělá |
|---|---|
| `db_query(query)` | libovolný SQL dotaz nad `agentdb` |
| `send_email(to, subject, body)` | `POST {MESSENGER_URL}/send` |
| `generate_weekly_report(teacher_name, lessons)` | poskládá text týdenního reportu |
| `generate_student_status_email(first_name, last_name, lessons)` | poskládá stavový e-mail studentovi |
| `process_teacher_reply(email_body)` | při „NESOUHLASÍM" v textu najde jména regexem a nastaví `internal.excused.approved = FALSE` |

## Konfigurace (env)

`MESSENGER_URL`, `DB_HOST`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_PORT`, `AGENT_PORT`
(viz `Security_agent/.env`, mimo git). V `docker-compose.yml` navíc `OLLAMA_HOST`
ukazuje na `http://lmstudio:1234` — nekonzistentní s `OLLAMA_URL` používaným
jinde v repu (`http://ollama:11434`) a agent ho ani nečte (`ollama` knihovna bere
host z vlastní konfigurace/env `OLLAMA_HOST` per balíček). Při ladění připojení
na LLM backend ověřit, co skutečně poslouchá na které adrese.

## Spuštění

```
cd Security_agent
pip install -r requirements.txt
python app/run_agent_service.py   # Flask na :8004 + scheduler thread
```

```bash
curl -X POST localhost:8004/run -H "Content-Type: application/json" \
  -d '{"email":"student@spssecb.cz","hour_id":123}'
```
