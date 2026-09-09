"""projektový systém – hierarchie, datová karta úkolu, time tracking, návrhy AI.

Databanka (§5) počítá s modulem „Projektový/task management systém (kanban)“.
Tahle migrace zakládá schéma `projects` pro službu `Projects`:

  workspaces → folders → projects → phases → tasks

Úkol nese datovou kartu dle dodané specifikace (1 hlavní řešitel + volitelní
spolupracovníci, 5stavový semafor, timeline, verze prototypu, finanční pole),
`time_entries` řeší stopky i ruční zápis a `proposals` drží návrhy změn od AI
(přes MCP), které čekají na schválení člověkem (§21 – nikdy nevratná akce bez
člověka).

Přidává i granulární oprávnění `projects.*` do katalogu `auth.permissions`
a mapuje je na systémové role (`admin` má `*`, takže se nevyjmenovává).

Revision ID: 0016_projects
Revises: 0015_auth_audit
Create Date: 2026-09-09

"""
from alembic import op

revision = "0016_projects"
down_revision = "0015_auth_audit"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# katalog oprávnění (schema.resource:action) + mapování na role
# ---------------------------------------------------------------------------
PERMISSIONS = [
    ("projects.project:read", "Číst složky, projekty a fáze."),
    ("projects.project:write", "Zakládat a upravovat složky, projekty a fáze."),
    ("projects.task:read", "Číst úkoly."),
    ("projects.task:write", "Zakládat a upravovat úkoly."),
    ("projects.task:assign", "Měnit řešitele a spolupracovníky úkolu."),
    ("projects.time:log", "Zapisovat vlastní odpracovaný čas."),
    ("projects.time:read_all", "Číst výkazy času všech uživatelů."),
    ("projects.finance:read", "Číst rozpočty, sazbu a součty nákladů."),
    ("projects.finance:write", "Měnit rozpočet a skutečné ceny."),
    ("projects.dashboard:read", "Číst manažerské dashboardy."),
    ("projects.ai:use", "Jednat se systémem přes MCP (AI napojení)."),
    ("projects.proposal:review", "Schvalovat a zamítat návrhy změn od AI."),
]

STAFF_PERMISSIONS = [name for name, _ in PERMISSIONS]  # staff = plný provozní rozsah

MEMBER_PERMISSIONS = [
    "projects.project:read",
    "projects.task:read",
    "projects.task:write",
    "projects.time:log",
    "projects.ai:use",
]


def _sql_str_list(values) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS projects;")

    op.execute(
        """
        CREATE TABLE projects.workspaces (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(128) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE projects.folders (
            id           SERIAL PRIMARY KEY,
            workspace_id INTEGER NOT NULL REFERENCES projects.workspaces(id) ON DELETE CASCADE,
            name         VARCHAR(128) NOT NULL,
            kind         VARCHAR(32) NOT NULL DEFAULT 'commercial',
            position     INTEGER NOT NULL DEFAULT 0,
            created_at   TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE projects.phase_templates (
            id       SERIAL PRIMARY KEY,
            name     VARCHAR(128) NOT NULL,
            position INTEGER NOT NULL
        );

        CREATE TABLE projects.projects (
            id                SERIAL PRIMARY KEY,
            folder_id         INTEGER NOT NULL REFERENCES projects.folders(id) ON DELETE CASCADE,
            name              VARCHAR(200) NOT NULL,
            description       TEXT,
            status            VARCHAR(16) NOT NULL DEFAULT 'active',
            planned_budget_czk NUMERIC,
            started_on        DATE,
            due_on            DATE,
            baseline_due_on   DATE,
            lead_user_id      INTEGER REFERENCES auth.users(id),
            created_by        INTEGER REFERENCES auth.users(id),
            created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE projects.phases (
            id         SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects.projects(id) ON DELETE CASCADE,
            name       VARCHAR(128) NOT NULL,
            position   INTEGER NOT NULL
        );
        CREATE INDEX idx_phases_project ON projects.phases (project_id);

        CREATE TABLE projects.tasks (
            id                SERIAL PRIMARY KEY,
            phase_id          INTEGER NOT NULL REFERENCES projects.phases(id) ON DELETE CASCADE,
            project_id        INTEGER NOT NULL REFERENCES projects.projects(id) ON DELETE CASCADE,
            title             VARCHAR(300) NOT NULL,
            description       TEXT,
            assignee_user_id  INTEGER REFERENCES auth.users(id),
            status            VARCHAR(16) NOT NULL DEFAULT 'backlog',
            start_on          DATE,
            due_on            DATE,
            baseline_due_on   DATE,
            proto_version     VARCHAR(32),
            estimated_hours   NUMERIC,
            cost_type         VARCHAR(16),
            estimated_cost_czk NUMERIC,
            actual_cost_czk   NUMERIC,
            order_status      VARCHAR(16),
            position          INTEGER NOT NULL DEFAULT 0,
            created_by        INTEGER REFERENCES auth.users(id),
            created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            done_at           TIMESTAMP
        );
        CREATE INDEX idx_tasks_phase ON projects.tasks (phase_id);
        CREATE INDEX idx_tasks_project ON projects.tasks (project_id);
        CREATE INDEX idx_tasks_assignee ON projects.tasks (assignee_user_id);

        CREATE TABLE projects.task_collaborators (
            task_id INTEGER NOT NULL REFERENCES projects.tasks(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, user_id)
        );

        CREATE TABLE projects.task_dependencies (
            task_id            INTEGER NOT NULL REFERENCES projects.tasks(id) ON DELETE CASCADE,
            depends_on_task_id INTEGER NOT NULL REFERENCES projects.tasks(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, depends_on_task_id),
            CHECK (task_id <> depends_on_task_id)
        );

        CREATE TABLE projects.time_entries (
            id         SERIAL PRIMARY KEY,
            task_id    INTEGER NOT NULL REFERENCES projects.tasks(id) ON DELETE CASCADE,
            user_id    INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            started_at TIMESTAMP NOT NULL,
            ended_at   TIMESTAMP,
            minutes    INTEGER,
            source     VARCHAR(16) NOT NULL DEFAULT 'timer',
            note       TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_time_entries_task ON projects.time_entries (task_id);
        CREATE INDEX idx_time_entries_user ON projects.time_entries (user_id);
        -- max jedny běžící stopky na uživatele
        CREATE UNIQUE INDEX uq_time_entries_running
            ON projects.time_entries (user_id) WHERE ended_at IS NULL;

        CREATE TABLE projects.settings (
            key   VARCHAR(64) PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE projects.proposals (
            id                  SERIAL PRIMARY KEY,
            requested_by_user_id INTEGER REFERENCES auth.users(id),
            origin              VARCHAR(16) NOT NULL DEFAULT 'mcp',
            kind                VARCHAR(48) NOT NULL,
            target_type         VARCHAR(32),
            target_id           INTEGER,
            payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
            summary             TEXT,
            status              VARCHAR(16) NOT NULL DEFAULT 'pending',
            reviewed_by_user_id INTEGER REFERENCES auth.users(id),
            reviewed_at         TIMESTAMP,
            review_note         TEXT,
            created_at          TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_proposals_status ON projects.proposals (status, created_at DESC);
        """
    )

    # --- seed: workspace + složky + šablona fází + nastavení -----------------
    op.execute(
        """
        INSERT INTO projects.workspaces (id, name) VALUES (1, 'Vývoj zařízení');
        SELECT setval('projects.workspaces_id_seq', 1, true);

        INSERT INTO projects.folders (workspace_id, name, kind, position) VALUES
            (1, 'Komerční prototypy', 'commercial', 1),
            (1, 'Interní R&D', 'internal_rnd', 2),
            (1, 'Globální přehledy', 'overview', 3);

        INSERT INTO projects.phase_templates (name, position) VALUES
            ('Koncept & Specifikace', 1),
            ('Vývoj & Návrh', 2),
            ('Nákupy & Logistika', 3),
            ('Výroba & Oživení', 4),
            ('Firmware & Integrace', 5);

        INSERT INTO projects.settings (key, value) VALUES
            ('hourly_rate_czk', '500'),
            ('weekly_capacity_hours', '40');
        """
    )

    # --- RBAC: katalog oprávnění + mapování na role -------------------------
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
    op.execute(
        f"""
        INSERT INTO auth.role_permissions (role_name, permission_name)
        SELECT 'member', name FROM auth.permissions
        WHERE name IN ({_sql_str_list(MEMBER_PERMISSIONS)});
        """
    )


def downgrade() -> None:
    all_perms = [name for name, _ in PERMISSIONS]
    op.execute(
        "DELETE FROM auth.role_permissions "
        f"WHERE permission_name IN ({_sql_str_list(all_perms)});"
    )
    op.execute(f"DELETE FROM auth.permissions WHERE name IN ({_sql_str_list(all_perms)});")
    op.execute("DROP SCHEMA IF EXISTS projects CASCADE;")
