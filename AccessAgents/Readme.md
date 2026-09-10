# AccessAgents

Agentní vrstva nad modulem **AccessRequest** (databanka §21). Samostatná služba
na portu **8007**: vlastní plánovač (APScheduler) + ruční spouštění agentů přes
HTTP. Rozhodovací fronta a reporty se schvalují/prohlížejí v `access-request-server`
(admin panel), tady se jen produkují.

## Vzor agenta

`trigger → data → LLM rozhodnutí → akce/návrh → audit log`, se čtyřmi úrovněmi
lidské kontroly (`ailacore.agents.ControlLevel`). Sdílený základ je v `ailacore`:

- `ailacore.llm` – LLM přes Ollamu (`OLLAMA_HOST`, `AILA_AGENT_MODEL`), `decide()`
  s bezpečným `_fallback`
- `ailacore.agents` – `emit_proposal` / `emit_flag` / `emit_report` /
  `record_agent_run` (audit ve stejné transakci)
- `ailacore.access_metrics` – agregační dotazy nad `internal.*`
- `ailacore.dukla` – rozvrh z duklamaps

Data + tabulky: sdílené schéma `agent` (`agent.proposals`, `agent.reports`),
migrace `0017_agent_layer`.

## Agenti

| name | trigger | úroveň | výstup |
|---|---|---|---|
| `monthly_lab_report` | 1. den v měsíci | pouze informuje + uloží | `agent.reports` + e-mail koordinátorům |

_(další – `subject_release_watch`, `release_advisor`, `registration_triage`,
`openhours_planner` – dle plánu.)_

## Endpointy

- `GET  /healthz` – stav, seznam agentů, naplánované joby
- `GET  /agents` – registr agentů
- `POST /run/{agent}` – ruční spuštění. Autorizace: přihlášený uživatel
  s `agent.run:trigger` (cookie/bearer), nebo `X-Agent-Token` shodný s
  `ACCESS_AGENT_RUN_TOKEN`.

## Konfigurace (env)

| Proměnná | Význam | Default |
|---|---|---|
| `ACCESS_AGENT_ENABLED` | **bezpečná brzda** – `false` = plánovač nezaregistruje joby | `false` |
| `OLLAMA_HOST` | Ollama server | `http://ollama:11434` |
| `AILA_AGENT_MODEL` | model | `llama3.2:8b-instruct` |
| `MESSENGER_URL` | služba pro odchozí e-maily | `http://messenger:8005` |
| `SCHEDULER_TZ` | pásmo plánovače | `Europe/Prague` |
| `MONTHLY_REPORT_DAY` / `MONTHLY_REPORT_HOUR` | čas #1 | `1` / `6` |
| `SUBJECT_RELEASE_STREAK` | práh #2 (hodin za sebou z předmětu) | `3` |
| `ACCESS_AGENT_RUN_TOKEN` | sdílený token pro `POST /run` bez session | `""` |
| `RELEASE_COORDINATOR_EMAILS` / `SUPERVISOR_EMAILS` | adresář koordinátorů | `""` |
| `DUKLA_PG_*`, `DUKLA_SUPERVISORS`, `DUKLA_DAY_BASE` | duklamaps rozvrh | viz compose |
| `POSTGRES_*` | sdílená `agentdb` (přes `ailacore.db`) | viz compose |

## Testy

```
cd AccessAgents && pip install -r requirements-dev.txt && pytest
```
