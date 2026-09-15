# AccessRequest

FastAPI služba pro registraci studentů, přihlašování, rezervace otevřených
hodin DuklaLabs a celý proces uvolňování z výuky (třídní/koordinátor souhlas →
zápis → rozhodnutí konkrétního vyučujícího/dozora → docházka). Vše nad
schématem `internal` (+ `auth`/`messaging`) v `agentdb`.

Běží na portu `8003`, šablony v `app/templates` (+ `app/templates/email` pro
e-mailové šablony), statika v `app/static`.

## Moduly (`app/`)

| Soubor | Co dělá |
|---|---|
| `auth.py` | Login (heslo i RFID), `POST /login/rfid`, `GET /api/whoami`. Sdílené SSO z `ailacore.auth`. |
| `students.py` | Registrace studenta, schvalování/zamítání nových účtů, `GET /api/students`. |
| `bookings.py` | Rezervace/zrušení otevřené hodiny studentem (`/api/book-hour`), kontrola kolize s vlastní výukou. |
| `open_hours.py` | Admin CRUD otevřených hodin + propis rozvrhu dozorů (viz níže). |
| `decisions.py` | Rozhodování o uvolnění (učitel/dozor přes podepsaný odkaz) + odklikávání docházky, rozesílací digesty. |
| `release.py` | Jednorázový souhlas třídního učitele a koordinátora s tím, že se student smí uvolňovat z výuky. |
| `excuse_requests.py` | Samostatný tokenový flow: potvrzení/zamítnutí konkrétní kolize hodiny konkrétním vyučujícím (individuálně i hromadně z týdenního digestu), + staff API pro tikety "učitel bez e-mailu". |
| `excuse_digest.py` | Týdenní e-mail (čtvrtek 12:00, plánovač v `main.py`) shrnující nevyřízené `internal.excuse_requests` danému učiteli. |
| `scheduler.py` | Druhý, nezávislý plánovač (APScheduler) pro `decisions.py`: rozhodovací digest (čt 13:00) + denní přehled docházky dozorům (7:00). |
| `mail_log.py` | Čtení `messaging.mail_log` (co a kdy Messenger skutečně odeslal). |
| `missing_teacher_tickets.py` | Tikety pro učitele z rozvrhu bez e-mailu (zapisuje `bookings.py`, řeší staff v `excuse_requests.py`). |
| `notify.py` | Sestavení a odeslání e-mailů přes Messenger (zápis, rozhodovací digesty, souhlas s uvolněním, rozhodnutí studentovi) + mapování jméno dozora → e-mail. |
| `mailer.py` | Přímý SMTP (bez Messengeru) pro `excuse_requests.py`/`excuse_digest.py` – vlastní šablony v `app/templates/email`. |
| `dukla_db.py` | Read-only klient do DB **duklamaps** pro propis dozorů v admin mřížce + dohledání třídního učitele/vyučujícího dané třídy+hodiny (`class_teachers`, `class_teacher`, `class_week`). |
| `timetable_client.py` | Druhý, nezávislý read-only klient do **téže** DB duklamaps (jiné env proměnné, jiná DB role) – používá ho jen `bookings.py` při zápisu na kolizi s výukou. |
| `router.py` | Stránky `/admin`, `/student-hours`; mountuje `bookings.py`. |
| `seed_demo.py` | `python -m app.seed_demo` – naseeduje demo studenty/hodiny/zápisy pro test procesu uvolňování. Idempotentní (smaže svá dřívější data). |
| `Agent.py` | Nepoužívaný pozůstatek staršího LLM-agentního flow (hardcoded SMTP heslo, mock lookup) – nikde importovaný, `main.py` ho nenačítá. |

`app/dukla_db.py` a `app/timetable_client.py` se připojují na **stejnou**
fyzickou DB (duklamaps, `host.docker.internal:5433`), ale odděleně – jiné env
proměnné (`DUKLA_PG_*` vs `TIMETABLE_DB_*`), jiná DB role, jiný účel: první
napájí admin mřížku (kdo z dozorů už učí), druhý řeší kolizi konkrétního
zápisu s výukou třídy v `bookings.py`. Nejde o duplicitu k odstranění bez
rozmyslu – historicky se to takhle vyvinulo, obě cesty se používají.

## Registrace a přihlášení

- `POST /student-register` (`students.py`) založí `auth.users` (role
  `student`, `is_active=FALSE`) i `internal.students` v jedné transakci a
  rovnou rozešle žádost o souhlas s uvolňováním třídnímu učiteli a
  koordinátorovi (`request_release_consent` → `notify.send_release_requests`).
  Dokud účet neschválí admin/staff (`POST /api/students/{user_id}/approve`),
  student se nepřihlásí.
- Login: `POST /login-check` (heslo, `auth.py`/`ailacore.auth`) i
  `POST /login/rfid` (čtečka jako HID klávesnice). Po loginu heslem směruje
  `admin`/`staff` na `/admin`, ostatní na `/student-hours`.

## Rezervace hodiny (`bookings.py`)

`POST /api/book-hour {hour_id}` (přihlášený student):

1. Zkontroluje kapacitu (`FOR UPDATE` na `internal.open_hours`, transakčně).
2. Pokud student ještě nemá schválené uvolňování (`release_teacher_ok AND
   release_coord_ok`), a v danou hodinu má podle rozvrhu třídy (přes
   `timetable_client.find_class_lesson`) vlastní výuku → 409, zápis odmítnut.
3. Pokud má schválené uvolňování, ale v danou hodinu koliduje s konkrétní
   vyučovanou hodinou → vytvoří se `internal.excuse_requests` (pending) pro
   konkrétního vyučujícího (přes `find_teacher_email`); pokud vyučující nemá
   v duklamaps e-mail, zápis rovnou selže (422) a založí se tiket
   (`missing_teacher_tickets.record_missing_teacher`).
4. Úspěšný zápis → `internal.bookings` insert (vlastní `decision_token`) a
   best-effort e-mail dozorovi (`notify.notify_booking`, jen když
   `NOTIFY_ON_BOOKING=true`).

Další endpointy: `GET /api/my-bookings`, `GET /api/my-lessons` (sloty vlastní
výuky pro zašednutí mřížky), `DELETE /api/book-hour/{hour_id}`.

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

### Ladění

`GET /api/open-hours/supervisions/debug` (staff/admin) vrací JSON se stavem
připojení, počty řádků v `timetable_*`, kolik řádků sedí na každého
nastaveného dozora a ukázku skutečných `teacher_name` v rozvrhu – podle toho
uprav `DUKLA_SUPERVISORS`. Chyby jdou i do logu kontejneru (`[dukla] ...`).

`GET /api/decisions/timetable-debug?class=4.ER&date=...&hour=...` (staff/
admin, `decisions.py`) ukazuje totéž z pohledu `dukla_db.class_teachers` –
diagnostika toho, kdo se dohledá jako vyučující dané třídy+hodiny.

## Uvolňování z výuky – tři na sebe navazující procesy

1. **Souhlas při registraci** (`release.py`, tabulka `internal.students`
   sloupce `release_teacher_ok`/`release_coord_ok`/`release_class_teacher`).
   Jednorázový, per-student. `GET/POST /uvolneni/{token}?role=tridni|
   koordinator&volba=ano|ne`. Třídní učitel se dohledá přes
   `dukla_db.class_teacher` (env `CLASS_TEACHERS` má přednost, jinak sloupec
   třídnictví `TEACHER_HOMEROOM_COLUMN` v `public.teachers`). Dokud
   **oba** nesouhlasí, `bookings.py` odmítne zápis na hodinu, kdy má student
   podle rozvrhu vlastní výuku. Staff API: `GET /api/students/release-pending`,
   `POST /api/students/{student_id}/release-coord`.

2. **Rozhodnutí o konkrétním zápisu** (`decisions.py`). I se schváleným
   uvolňováním z bodu 1 zůstává v hitparádě rozhodnutí konkrétní vyučující
   (nebo dozor, pokud vyučující nejde dohledat) – `internal.bookings.approved`
   (NULL/TRUE/FALSE) + `attended` (docházka). Cesty:
   - `GET/POST /rozhodovani/{token}` – hromadná stránka pro učitele
     (jen svoji studenti) nebo dozora (všechny jeho hodiny po dnech +
     docházka), token = `notify.decision_token(kind, name)` (HMAC,
     `DECISION_SECRET`), bez přihlášení.
   - `GET/POST /rozhodnuti/{token}` – jednorázový odkaz na **jedno**
     rozhodnutí, jen když `NOTIFY_ON_BOOKING=true` (token uložený přímo
     na řádku `internal.bookings.decision_token`).
   - `POST /api/decisions/send-digest` / `send-supervisor-roster` /
     `run-teacher-digest` / `run-supervisor-roster` (`internal.release:manage`)
     – ruční spuštění stejných úloh, které jinak běží podle plánovače
     v `scheduler.py`.

3. **Omluvenka ke konkrétní kolizi** (`excuse_requests.py`,
   `internal.excuse_requests` + `internal.lesson_hours` +
   `internal.excuse_digest_batches`/`_batch_items`). Založí ji `bookings.py`
   při zápisu, když student má schválené obecné uvolňování (bod 1), ale
   konkrétní termín koliduje s konkrétní vyučovanou hodinou – místo
   automatického zápisu čeká na potvrzení tím vyučujícím:
   - `GET/POST /excuse-requests/{token}(/approve|/deny)` – jedna žádost.
   - `GET/POST /excuse-requests/batch/{batch_token}(/approve-all|/deny-all)`
     – hromadně ze souhrnného e-mailu (viz `excuse_digest.py`, čtvrtek 12:00,
     naplánovaný přímo v `main.py`, **nezávisle** na plánovači v `scheduler.py`).
   - Zamítnutí zruší booking (`cancelled_at`/`cancelled_reason='excuse_denied'`),
     schválení zapíše `internal.excused`. Studentovi jde e-mail
     (`app/templates/email/student_approved.html` / `student_denied.html`).
   - Staff API pro tikety "vyučující bez e-mailu":
     `GET /api/excuse-requests/missing-teacher-tickets`,
     `POST /api/excuse-requests/missing-teacher-tickets/{id}/resolve`
     (`require_role("admin","staff")`, ne granulární RBAC).

Procesy 2 a 3 jsou **oddělené kódové cesty s vlastními tokeny/tabulkami** a
běží na dvou nezávislých APScheduler instancích (`main.py` startup pro
excuse_digest, `scheduler.py` pro decisions) – při ladění rozeslaných mailů
ověřuj, který z obou digestů je v ruce (`GET /api/decisions/scheduler` ukazuje
jen tu druhou).

## Mail log a notifikace

- `GET /api/mail-log?limit=&status=&to=&q=` (`messaging.mail_log:read`) –
  čtení `messaging.mail_log` (zapisuje ho Messenger), s filtrem a součty
  podle stavu. Ověření, že (a kdy) mail skutečně odešel.
- Dvě nezávislé cesty odesílání e-mailu:
  - `notify.py` → přes Messenger (`POST {MESSENGER_URL}/send`), používá se
    pro zápis na hodinu, rozhodovací digesty, souhlas s uvolněním a
    rozhodnutí studentovi. Loguje se do `messaging.mail_log`.
  - `mailer.py` → přímé SMTP (`smtplib`, `app/templates/email/*.html` přes
    `jinja2`), používá `excuse_requests.py`/`excuse_digest.py`. **Nejde**
    přes Messenger, takže se v `messaging.mail_log` neobjeví. Bez
    `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` v env spadne s `KeyError` hned
    při prvním pokusu o odeslání (záměrně – radši hlasitě než tiše nikam).

## RBAC

Guardy jsou přes `ailacore.rbac.require_permission` (granulární) až na
`excuse_requests.py`, který používá hrubší `ailacore.auth.require_role("admin",
"staff")`.

| oprávnění | kde |
|---|---|
| `internal.open_hours:read` / `:write` | `open_hours.py`, admin mřížka |
| `internal.booking:read` | `open_hours.py` – kdo je zapsaný na hodinu |
| `internal.student:read` / `:write` | `students.py` – schvalování registrací |
| `internal.release:manage` | `release.py`, `decisions.py` – souhlasy, rozesílání digestů |
| `messaging.mail_log:read` | `mail_log.py` |

Sdílená RBAC administrace (`ailacore.admin`) je zamountovaná v `main.py`:
`app.include_router(rbac_api_router)` + `mount_admin_ui(app,
os.getenv("RBAC_UI_DIST", "rbac-ui-dist"))` → JSON API pod `/api/rbac`,
React konzole na `/admin/rbac/`. Dockerfile má vlastní `rbac-ui` build stage
(Node, `UI/` → `npm run build` → `COPY --from=rbac-ui /ui/dist
/app/rbac-ui-dist`) – referenční vzor pro ostatní služby (viz `Shared/README.md`).

## Plánované úlohy (APScheduler, in-process)

Dvě nezávislé instance:

- `main.py` (startup): `weekly_excuse_digest` – čtvrtek 12:00, volá
  `excuse_digest.run_weekly_digest()`.
- `app/scheduler.py`, `start_scheduler()` volané z `main.py` startup:
  `teacher-digest` (`TEACHER_DIGEST_DOW`/`_HOUR`/`_MINUTE`, default čt 13:00)
  a `supervisor-roster` (`SUPERVISOR_ROSTER_HOUR`/`_MINUTE`, default denně
  7:00). `SCHEDULER_ENABLED=false` obě úlohy v tomto modulu vypne (ne tu
  z `main.py`). `GET /api/decisions/scheduler` (`internal.release:manage`)
  vrátí naplánované joby + čas příštího běhu – jen pro `scheduler.py`.

Obě instance jsou `AsyncIOScheduler` (ne `BackgroundScheduler`) – joby volají
asyncpg přes pool navázaný na běžící event loop uvicornu, `BackgroundScheduler`
by do něj sahal z jiného vlákna. Předpokládá se jedna replika
`access-request-server`; škálování na víc instancí by potřebovalo distribuovaný
zámek proti duplicitním digestům.

## Konfigurace (env)

Většina proměnných je přímo v `docker-compose.yml` (služba
`access-request-server`, komentáře u každé). SMTP a `PUBLIC_BASE_URL` navíc
jdou přes `env_file: AccessRequest/.env` (vzor v `AccessRequest/.env.example`,
`.env` je gitignored).

| Proměnná | Význam | Default |
|---|---|---|
| `MESSENGER_URL` | Kam `notify.py` posílá e-maily | `http://messenger:8005` |
| `SUPERVISOR_EMAILS` | Mapa jméno→e-mail dozora, `"Jméno=email; ..."`, páruje se s `DUKLA_SUPERVISORS` | `""` |
| `PUBLIC_BASE_URL` | Veřejná URL pro odkazy v e-mailech (rozhodování, uvolnění) | `http://localhost:8003` |
| `DECISION_SECRET` | HMAC klíč pro `/rozhodovani/{token}` odkazy | `dev-decision-secret-change-me` |
| `NOTIFY_ENABLED` | Vypne úplně odchozí e-maily z `notify.py` | `true` |
| `NOTIFY_ON_BOOKING` | Okamžitý e-mail dozorovi při každém zápisu (jinak jen souhrnný digest) | `false` |
| `BOOKING_NOTIFY_CC` | Nepovinná kopie u notifikací z `notify.py` | `""` |
| `RELEASE_COORDINATOR_EMAILS` | Koordinátor(ři) uvolňování; prázdné = adresy z `SUPERVISOR_EMAILS` | `""` |
| `TEACHER_EMAIL_DOMAIN` | Doména pro odvození e-mailu učitele bez e-mailu v duklamaps | `spssecb.cz` |
| `TEACHER_EMAIL_OVERRIDES` | Ruční mapa jméno→e-mail, `"Příjmení Jméno=mail; ..."`, má přednost před duklamaps | `""` |
| `CLASS_TEACHERS` | Ruční mapa třída→třídní učitel, `"4.ER=Hána Jiří; ..."`, má přednost před `TEACHER_HOMEROOM_COLUMN` | `""` |
| `TEACHER_HOMEROOM_COLUMN` | Sloupec třídnictví v duklamaps `public.teachers` | `homeroom_class` |
| `SCHEDULER_ENABLED` | Zapíná/vypíná joby v `app/scheduler.py` (ne ten z `main.py`) | `true` |
| `SCHEDULER_TZ` | Časové pásmo obou plánovačů | `Europe/Prague` |
| `TEACHER_DIGEST_DOW`/`_HOUR`/`_MINUTE` | Kdy jde rozhodovací digest učitelům (`scheduler.py`) | `thu` / `13` / `0` |
| `SUPERVISOR_ROSTER_HOUR`/`_MINUTE` | Kdy jde denní přehled docházky dozorům | `7` / `0` |
| `DUKLA_PG_HOST`/`PORT`/`DB`/`USER`/`PASSWORD` | Připojení do duklamaps pro admin mřížku (`dukla_db.py`). Prázdné `DUKLA_PG_HOST` = propis vypnutý | `""` / `5432` / `DL_access_manager` / `postgres` / `""` |
| `DUKLA_SUPERVISORS` | Čárkou oddělená jména dozorů, matchuje se po slovech bez titulů | `""` |
| `DUKLA_DAY_BASE` | Hodnota `day_index` pro pondělí (0 nebo 1) | `0` |
| `DUKLA_PERMANENT_FALLBACK` | `1` = prázdný týden spadne na `timetable_permanent` | `0` |
| `TIMETABLE_DB_HOST`/`PORT`/`NAME`/`USER`/`PASSWORD` | Druhé, nezávislé připojení do (typicky téže) duklamaps DB pro kontrolu kolize při zápisu (`timetable_client.py`), role jen na `SELECT` | `access_request_ro` / `""` / `duklamaps` / `host.docker.internal` / `5433` |
| `SMTP_HOST`/`PORT`/`USER`/`PASSWORD`/`FROM_ADDR`/`FROM_NAME` | Přímé SMTP pro `mailer.py` (omluvenky) – `.env`, ne docker-compose | povinné mimo `PORT`(`587`)/`FROM_NAME`(`DuklaLabs`) |
| `RBAC_UI_DIST` | Kde hledat buildnutou RBAC konzoli (`ailacore.admin`) | `rbac-ui-dist` |

## Vývoj

```
# DB (jednou, z Database/)
cd Database && POSTGRES_HOST=localhost alembic upgrade head

cd AccessRequest
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8003

# demo data pro proces uvolňování (volitelné)
python -m app.seed_demo
```

Bez nakonfigurovaného `DUKLA_PG_HOST`/`TIMETABLE_DB_*` (duklamaps) běží
mřížka i zápisy dál, jen bez propisu rozvrhu a bez kontroly kolize s výukou.
Bez `SMTP_HOST` v `.env` spadne jen odesílání omluvenek
(`excuse_requests.py`/`excuse_digest.py`); zbytek notifikací (přes Messenger)
funguje nezávisle na tom.
