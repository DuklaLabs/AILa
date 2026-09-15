"""agentní vrstva nad platformou (§21 databanky) – sdílené tabulky.

Databanka §21 počítá s „agentní vrstvou": agenti nad hotovými moduly podle vzoru
**trigger → data → LLM rozhodnutí → akce/návrh → audit log** se čtyřmi úrovněmi lidské
kontroly. Základ je sdílený (`ailacore.agents`), ať ho používají agenti všech modulů,
ne aby si každý modul zakládal vlastní tabulku.

Zakládá schéma `agent`:

  - `agent.proposals` – návrhy a upozornění od agentů. `status='pending'` čeká na
    schválení člověkem (`agent.proposal:review`), `status='info'` je jen vlajka na
    vědomí (neschvaluje se). `module` odlišuje, z kterého modulu agent pochází.
  - `agent.reports`   – uložené periodické reporty (měsíční přehledy apod.),
    jeden řádek na (`module`, `period`).

Přidává granulární oprávnění `agent.*` do katalogu `auth.permissions`
(`admin` má `*`, takže se nevyjmenovává).

Revision ID: 0017_agent_layer
Revises: 0016_projects
Create Date: 2026-09-10

"""
from alembic import op

revision = "0017_agent_layer"
down_revision = "0016_projects"
branch_labels = None
depends_on = None


PERMISSIONS = [
    ("agent.proposal:review", "Schvalovat a zamítat návrhy od agentů."),
    ("agent.report:read", "Číst periodické reporty agentů."),
    ("agent.run:trigger", "Ručně spustit agenta (mimo plánovač)."),
    ("agent:configure", "Měnit konfiguraci agentní vrstvy."),
]

# staff = plný provozní rozsah kromě konfigurace samotné vrstvy
STAFF_PERMISSIONS = [
    "agent.proposal:review",
    "agent.report:read",
    "agent.run:trigger",
]


def _sql_str_list(values) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS agent;")

    op.execute(
        """
        CREATE TABLE agent.proposals (
            id                  BIGSERIAL PRIMARY KEY,
            module              TEXT NOT NULL,          -- 'access', ...
            agent               TEXT NOT NULL,          -- 'registration_triage', ...
            kind                TEXT NOT NULL,          -- 'registration.approve', ...
            target_type         TEXT,
            target_id           TEXT,
            payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
            summary             TEXT,
            confidence          NUMERIC,
            status              TEXT NOT NULL DEFAULT 'pending',
                                -- pending | approved | rejected | info
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            reviewed_by_user_id INTEGER REFERENCES auth.users(id),
            reviewed_at         TIMESTAMPTZ,
            review_note         TEXT
        );
        CREATE INDEX ix_agent_proposals_queue
            ON agent.proposals (module, status, created_at DESC);

        CREATE TABLE agent.reports (
            id           BIGSERIAL PRIMARY KEY,
            module       TEXT NOT NULL,
            period       DATE NOT NULL,                 -- 1. den měsíce apod.
            payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
            summary      TEXT,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (module, period)
        );
        """
    )

    perm_values = ", ".join(
        "('" + name.replace("'", "''") + "', '" + desc.replace("'", "''") + "')"
        for name, desc in PERMISSIONS
    )
    op.execute(
        f"INSERT INTO auth.permissions (name, description) VALUES {perm_values};"
    )
    op.execute(
        f"""
        INSERT INTO auth.role_permissions (role_name, permission_name)
        SELECT 'staff', name FROM auth.permissions
        WHERE name IN ({_sql_str_list(STAFF_PERMISSIONS)});
        """
    )


def downgrade() -> None:
    all_perms = [name for name, _ in PERMISSIONS]
    op.execute(
        "DELETE FROM auth.role_permissions "
        f"WHERE permission_name IN ({_sql_str_list(all_perms)});"
    )
    op.execute(f"DELETE FROM auth.permissions WHERE name IN ({_sql_str_list(all_perms)});")
    op.execute("DROP SCHEMA IF EXISTS agent CASCADE;")
