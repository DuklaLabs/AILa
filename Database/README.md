# Database

Schema pro sdílenou Postgres instanci (`agentdb`), spravované přes Alembic migrace v `migrations/`. Ruční `init.sql` je jen historická reference, Postgres kontejner ho už automaticky nespouští.

## Nastavení schématu (čistá DB)

```
docker compose up -d postgres
cd Database
pip install -r requirements.txt
alembic upgrade head
```

Proměnné prostředí (stejné jako v `docker-compose.yml`): `POSTGRES_HOST`, `POSTGRES_PORT` (default `5432`), `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.

## Nová migrace

```
cd Database
alembic revision -m "popis změny"
```

Migrace jsou psané jako čisté SQL přes `op.execute(...)` (žádné ORM modely), viz `migrations/versions/0001_baseline.py` pro vzor.

## Schémata a stav migrací

`0001_baseline` založí schémata `auth`, `inventory`, `lab`, `orders`, `events`,
`internal`. `0013_mail_log` přidává `messaging`, `0016_projects` přidává
`projects`, `0017_agent_layer` přidává `agent`, `0019_general_chat` přidává
`general` (konverzace s Generálem pod účtem, viz `General/Readme`).

**`0018_merge_heads`** sjednocuje dvě větve, co obě navazovaly na
`0016_projects` (`0009_excuse_workflow` a `0017_agent_layer` – vznikly
nezávisle, žádná neexistovala, když druhá vznikala). Bez merge revize
`alembic upgrade head` spadne na "Multiple head revisions". Objevilo se to,
když `db-migrate` kontejner dlouho běžel proti staršímu image (bez
`0017_agent_layer` v souborech), takže nikdy nehlásil chybu – teprve po
přebuildu vyšlo najevo, že `alembic_version` v `agentdb` ukazoval na
`0009_excuse_workflow`, ale schémata `messaging`/`projects`/RBAC katalog
(`0013`–`0016`) na produkční DB reálně nikdy neběžela (historie migrací se
mezitím přeuspořádala, aniž by se to nasadilo). Dohnáno ručně (viz git
historie `0018`/`0019` pro detaily) – `alembic upgrade head` teď na čerstvé
i na tehdy postižené DB funguje čistě.

**Pozor na pořadí souborů vs. skutečný alembic řetězec.** Číselný prefix v
názvu souboru je jen orientační (kdy migrace vznikla), skutečné pořadí
uplatnění určuje `down_revision` v každém souboru. Dvě dvojice `0008_*`
a `0009_*` existují souběžně ve dvou různých větvích historie:

- `0008_open_hours_supervisor` → `0009_open_hours_supervisor_multi` navazují
  lineárně na `0007_open_hours_unique_slot` (early historie otevřených hodin).
- `0008_lesson_hours_dedup` má `down_revision = "0016_projects"` – je tedy
  v řetězu **až po** `0016_projects`, ne před ním. Po něm následuje
  `0009_excuse_workflow` (omluvenkový approval flow, `internal.excuse_requests`
  + `excuse_digest_batches`/`_batch_items` + `missing_teacher_tickets` +
  soft-cancel na `internal.bookings`) – to je **aktuální head** migrací, ne
  `0016_projects`. Při pochybnostech o skutečném pořadí věř `down_revision`
  řetězci (nebo `alembic history`), ne názvu souboru.

## RBAC katalog

Granulární oprávnění žijí v `auth.roles` / `auth.permissions` / `auth.role_permissions`
(+ `auth.user_roles`, `auth.user_permissions`). Katalog i mapování systémových rolí
seeduje migrace `0014_rbac`; nové oprávnění se přidává vlastní migrací (insert do
`auth.permissions` a `auth.role_permissions`). Runtime kontrola je `ailacore.rbac`.
