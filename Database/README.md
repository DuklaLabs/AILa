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

## RBAC katalog

Granulární oprávnění žijí v `auth.roles` / `auth.permissions` / `auth.role_permissions`
(+ `auth.user_roles`, `auth.user_permissions`). Katalog i mapování systémových rolí
seeduje migrace `0014_rbac`; nové oprávnění se přidává vlastní migrací (insert do
`auth.permissions` a `auth.role_permissions`). Runtime kontrola je `ailacore.rbac`.
