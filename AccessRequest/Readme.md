# AccessRequest

FastAPI služba pro registraci studentů, přihlašování a správu otevřených
hodin (`internal.open_hours` + `internal.bookings` v `agentdb`).

Běží na portu `8003`, šablony v `app/templates`, statika v `app/static`.

## Otevřené hodiny – admin mřížka

`/admin` zobrazuje týdenní mřížku (Po–Pá × vyučovací hodiny 0–10) s
přepínačem týdne:

- **Tento týden = přehled** (read-only). Buňka s otevřenou hodinou je
  klikací → modal se seznamem přihlášených studentů (jméno, příjmení,
  třída) + přiřazený dozor a poznámka. Nic se tu needituje. Hodiny
  kolegů z rozvrhu (duklamaps) se zobrazí i pod už zadanou volnou hodinou.
- **Příští týden = plánování.** V prázdné buňce `+` → inline formulář
  (kapacita, **výběr jednoho i více dozorů** z `DUKLA_SUPERVISORS`
  zaškrtávátky, poznámka). U uložené hodiny ✏️ (úprava kapacity/dozorů/
  poznámky) a × (smazání).
- **Volná hodina musí mít aspoň jednoho dozora** (pokud je `DUKLA_SUPERVISORS`
  nastavené) – vynucuje frontend i `POST /add` / `PATCH /{id}` (400).
- **Dozor nesmí mít v tu hodinu vlastní výuku.** Kdo v dané buňce podle
  rozvrhu (duklamaps) učí, má v formuláři zaškrtávátko zakázané a `POST
  /add` i `PATCH /{id}` takové přiřazení odmítnou (400). Když duklamaps
  není dostupná, kontrola se přeskočí (nejde ověřit → neblokuje se).

API v `app/open_hours.py`: `GET /api/open-hours/{periods,list,supervisors,supervisions}`,
`GET /api/open-hours/supervisions/debug`, `GET /api/open-hours/{id}/bookings`,
`POST /api/open-hours/add`, `PATCH /api/open-hours/{id}`,
`DELETE /api/open-hours/delete/{id}`. Sloupec `internal.open_hours.supervisor`
(migrace 0008, rozšířen na `TEXT` v 0009) drží přiřazené dozory jako
čárkou oddělený seznam.

## Propis dozorujících učitelů (duklamaps DB)

Do prázdných buněk se propisují hodiny, kdy má vybraný dozor vlastní výuku
(je „blokovaný"), z **oddělené** databáze scrapnutého Bakalářského rozvrhu
(jiný Postgres než `agentdb`). Čte se jen pro čtení přes `app/dukla_db.py`.

Očekávané schéma (`public.timetable_actual` / `timetable_next` /
`timetable_permanent`): `week_date` (pondělí daného týdne), `entity_type`,
`day_index`, `hour_index`, `teacher_name`, `subject_name`/`subject_abbrev`,
`class_abbrev`, `room_abbrev`, `change_type`. Přepínač *Tento / Příští týden*
v mřížce vybírá `timetable_actual` vs `timetable_next`; když je týdenní
tabulka prázdná, spadne se na `timetable_permanent`.

Každý nastavený dozor je v buňce **samostatný barevný blok** a nad mřížkou
je filtr (chipy), kterým se jednotliví dozoři zapínají/vypínají. Seznam
jmen dává `GET /api/open-hours/supervisors`; `GET /api/open-hours/supervisions`
vrací u každého řádku `supervisor` = to nastavené jméno, ke kterému patří.

Konfigurace přes env (viz `docker-compose.yml`, služba `access-request-server`):

| Proměnná | Význam | Default |
|---|---|---|
| `DUKLA_PG_HOST` | host duklamaps Postgresu; **prázdné = funkce vypnutá**. Uvnitř kontejneru je `localhost` kontejner sám – pro DB na tvém stroji použij `host.docker.internal` | `""` |
| `DUKLA_PG_PORT` | port | `5432` |
| `DUKLA_PG_DB` | název databáze | `DL_access_manager` |
| `DUKLA_PG_USER` / `DUKLA_PG_PASSWORD` | přihlášení | `postgres` / `""` |
| `DUKLA_SUPERVISORS` | čárkou oddělený seznam jmen dozorů; matchuje se **po slovech bez ohledu na pořadí a tituly** (`Bc. Jan Petrášek` = `Petrášek Jan`) | `""` |
| `DUKLA_DAY_BASE` | hodnota `day_index` pro pondělí (0 nebo 1) | `0` |
| `DUKLA_PERMANENT_FALLBACK` | `1` = když `timetable_actual`/`_next` pro daný týden nic nemá, použij stálý rozvrh `timetable_permanent`. `0` = prázdný týden zůstane prázdný (prázdniny). | `0` |

Data se berou přesně podle `week_date` (pondělí zvoleného týdne): „Tento týden"
= `timetable_actual`, „Příští týden" = `timetable_next`. Žádný automatický
fallback na stálý rozvrh (leda přes `DUKLA_PERMANENT_FALLBACK=1`).

Když je DB nedostupná nebo nenakonfigurovaná, endpoint `/supervisions`
vrací `[]` a mřížka funguje normálně bez propisu.

### Ladění

`GET /api/open-hours/supervisions/debug` (staff/admin) vrací JSON se stavem
připojení, počty řádků v `timetable_*`, kolik řádků sedí na každého
nastaveného dozora a ukázku skutečných `teacher_name` v rozvrhu – podle toho
uprav `DUKLA_SUPERVISORS`. Chyby jdou i do logu kontejneru (`[dukla] ...`).
