"""granulární RBAC – katalog oprávnění, mapování na role, per-user granty.

Databanka (sekce 18) řadí jednotný granulární systém rolí a oprávnění do jádra
(Vlna 0). Do teď uměl `ailacore.auth.require_role` jen porovnat jeden řetězec
`auth.users.role`; tabulka `auth.permissions` z baseline nikdy nikdo nečetl.

Tahle migrace:
  - přejmenuje nevyužitou `auth.permissions` → `auth.user_permissions` (per-user
    granty, prázdná, takže ALTERy jsou bezpečné) a přetvaruje ji,
  - zavede katalog `auth.permissions` (name = 'schema.resource:action'),
  - zavede `auth.roles`, `auth.role_permissions`, `auth.user_roles`
    (`auth.users.role` zůstává jako *primární* role, user_roles jsou navíc),
  - naseeduje systémové role, startovní katalog oprávnění a mapování rolí tak,
    aby `admin` = vše (`*`) a `staff` odpovídal dnešnímu `require_role("admin","staff")`.

Revision ID: 0014_rbac
Revises: 0013_mail_log
Create Date: 2026-09-08

"""
from alembic import op

revision = "0014_rbac"
down_revision = "0013_mail_log"
branch_labels = None
depends_on = None


# Startovní katalog oprávnění (schema.resource:action). Další služby si své
# oprávnění přidají vlastní budoucí migrací.
PERMISSIONS = [
    ("*", "Zástupný symbol pro všechna oprávnění (drží ho role admin)."),
    ("auth.user:read", "Číst účty uživatelů."),
    ("auth.user:write", "Zakládat a upravovat účty uživatelů."),
    ("auth.role:manage", "Spravovat role a jejich oprávnění."),
    ("auth.permission:grant", "Přidělovat oprávnění přímo uživateli."),
    ("internal.open_hours:read", "Číst otevřené hodiny."),
    ("internal.open_hours:write", "Spravovat otevřené hodiny a jejich dozor."),
    ("internal.booking:read", "Číst rezervace studentů na otevřené hodiny."),
    ("internal.booking:decide", "Schvalovat/zamítat rezervace, zapisovat docházku."),
    ("internal.student:read", "Číst evidenci studentů."),
    ("internal.student:write", "Upravovat evidenci studentů."),
    ("internal.release:manage", "Spravovat uvolňování studentů z výuky."),
    ("messaging.mail_log:read", "Číst log odeslané pošty."),
    ("messaging.mail:send", "Odesílat e-maily přes sdílenou poštovní službu."),
    ("inventory.item:read", "Číst skladové položky."),
    ("inventory.item:write", "Zakládat a upravovat skladové položky."),
    ("inventory.stock:adjust", "Měnit stav zásob."),
    ("orders.order:read", "Číst objednávky."),
    ("orders.order:create", "Vytvářet objednávky."),
    ("orders.order:approve", "Schvalovat objednávky."),
    ("lab.reservation:read", "Číst rezervace strojů."),
    ("lab.reservation:write", "Vytvářet a rušit rezervace strojů."),
    ("lab.machine:manage", "Spravovat evidenci strojů."),
]

SYSTEM_ROLES = [
    ("admin", "Plný přístup ke všem modulům."),
    ("staff", "Provozní personál laborky (učitelé, koordinátoři)."),
    ("member", "Přihlášený člen bez zvláštních oprávnění."),
    ("student", "Studentský účet (přístup řešený doménově, ne přes oprávnění)."),
    ("public", "Externí zájemce / veřejnost."),
]

# staff = dnešní rozsah require_role("admin","staff") + čtení napříč ostatními moduly
STAFF_PERMISSIONS = [
    "internal.open_hours:read",
    "internal.open_hours:write",
    "internal.booking:read",
    "internal.booking:decide",
    "internal.student:read",
    "internal.student:write",
    "internal.release:manage",
    "messaging.mail_log:read",
    "messaging.mail:send",
    "inventory.item:read",
    "orders.order:read",
    "lab.reservation:read",
]


def _sql_str_list(values) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def upgrade() -> None:
    # 1) nevyužitá auth.permissions -> auth.user_permissions (per-user granty)
    op.execute(
        """
        ALTER TABLE auth.permissions RENAME TO user_permissions;
        ALTER TABLE auth.user_permissions DROP COLUMN resource_type;
        ALTER TABLE auth.user_permissions RENAME COLUMN permission TO permission_name;
        ALTER TABLE auth.user_permissions
            ADD COLUMN granted_by INTEGER REFERENCES auth.users(id);
        ALTER TABLE auth.user_permissions
            ALTER COLUMN permission_name SET NOT NULL;
        ALTER TABLE auth.user_permissions
            ADD CONSTRAINT uq_user_permissions_grant
            UNIQUE (user_id, permission_name, resource_id);
        """
    )

    # 2) katalog oprávnění
    op.execute(
        """
        CREATE TABLE auth.permissions (
            name        VARCHAR(96) PRIMARY KEY,
            description TEXT,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
    )

    # 3) katalog rolí
    op.execute(
        """
        CREATE TABLE auth.roles (
            name        VARCHAR(32) PRIMARY KEY,
            description TEXT,
            is_system   BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
    )

    # 4) role -> oprávnění (M:N)
    op.execute(
        """
        CREATE TABLE auth.role_permissions (
            role_name       VARCHAR(32) NOT NULL REFERENCES auth.roles(name) ON DELETE CASCADE,
            permission_name VARCHAR(96) NOT NULL REFERENCES auth.permissions(name) ON DELETE CASCADE,
            PRIMARY KEY (role_name, permission_name)
        );
        """
    )

    # 5) uživatel -> sekundární role (auth.users.role zůstává primární)
    op.execute(
        """
        CREATE TABLE auth.user_roles (
            user_id    INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            role_name  VARCHAR(32) NOT NULL REFERENCES auth.roles(name) ON DELETE CASCADE,
            granted_by INTEGER REFERENCES auth.users(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, role_name)
        );
        """
    )

    # doplnit FK z user_permissions.permission_name do katalogu (katalog už existuje)
    op.execute(
        """
        ALTER TABLE auth.user_permissions
            ADD CONSTRAINT fk_user_permissions_permission
            FOREIGN KEY (permission_name) REFERENCES auth.permissions(name) ON DELETE CASCADE;
        """
    )

    # 6) seed katalogu oprávnění
    perm_values = ", ".join(
        "('" + name.replace("'", "''") + "', '" + desc.replace("'", "''") + "')"
        for name, desc in PERMISSIONS
    )
    op.execute(
        f"INSERT INTO auth.permissions (name, description) VALUES {perm_values};"
    )

    # 7) seed systémových rolí + backfill rolí, které už na účtech jsou
    role_values = ", ".join(
        "('" + name.replace("'", "''") + "', '" + desc.replace("'", "''") + "', TRUE)"
        for name, desc in SYSTEM_ROLES
    )
    op.execute(
        f"INSERT INTO auth.roles (name, description, is_system) VALUES {role_values};"
    )
    op.execute(
        """
        INSERT INTO auth.roles (name, is_system)
        SELECT DISTINCT role, FALSE FROM auth.users
        WHERE role IS NOT NULL
        ON CONFLICT (name) DO NOTHING;
        """
    )

    # FK auth.users.role -> auth.roles(name) (po backfillu nemůže selhat)
    op.execute(
        """
        ALTER TABLE auth.users
            ADD CONSTRAINT fk_users_role FOREIGN KEY (role) REFERENCES auth.roles(name);
        """
    )

    # 8) mapování rolí na oprávnění
    op.execute(
        "INSERT INTO auth.role_permissions (role_name, permission_name) VALUES ('admin', '*');"
    )
    op.execute(
        f"""
        INSERT INTO auth.role_permissions (role_name, permission_name)
        SELECT 'staff', name FROM auth.permissions
        WHERE name IN ({_sql_str_list(STAFF_PERMISSIONS)});
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE auth.users DROP CONSTRAINT IF EXISTS fk_users_role;")
    op.execute("DROP TABLE IF EXISTS auth.user_roles;")
    op.execute("DROP TABLE IF EXISTS auth.role_permissions;")
    op.execute("DROP TABLE IF EXISTS auth.roles;")

    # katalog musí padnout dřív, než se user_permissions přejmenuje zpět na
    # "permissions" – jinak koliduje název tabulky
    op.execute(
        "ALTER TABLE auth.user_permissions "
        "DROP CONSTRAINT IF EXISTS fk_user_permissions_permission;"
    )
    op.execute("DROP TABLE IF EXISTS auth.permissions;")

    op.execute(
        """
        ALTER TABLE auth.user_permissions
            DROP CONSTRAINT IF EXISTS uq_user_permissions_grant;
        ALTER TABLE auth.user_permissions DROP COLUMN IF EXISTS granted_by;
        ALTER TABLE auth.user_permissions ALTER COLUMN permission_name DROP NOT NULL;
        ALTER TABLE auth.user_permissions RENAME COLUMN permission_name TO permission;
        ALTER TABLE auth.user_permissions ADD COLUMN resource_type VARCHAR(64);
        ALTER TABLE auth.user_permissions RENAME TO permissions;
        """
    )
