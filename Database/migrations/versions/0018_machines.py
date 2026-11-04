"""lab.machines: stav stroje a kdo ho právě používá.

Databanka (sekce 9/21, "kontrola strojů") chce jedno místo s přehledem
provozu strojů. `lab.machines` z baseline měl jen statickou evidenci (název,
typ, umístění) – chybí provozní stav. Nejde o rezervace (`lab.reservation:*`
pokrývá domluvené termíny), ale o "co se děje se strojem právě teď".

`lab.machine:manage` je v katalogu oprávnění od 0014_rbac, ale nikdy nebyl
přiřazen roli `staff` (jen `admin` ho měl přes `*`) – bez toho by provozní
personál nemohl stav strojů měnit. Čtení stavu nemá vlastní oprávnění,
stejně jako /student-hours: stačí přihlášení (ať vidí stav stroje i
studenti, ne jen staff).

Revision ID: 0018_machines
Revises: 0017_agent_layer
Create Date: 2026-11-04

"""
from alembic import op

revision = "0018_machines"
down_revision = "0017_agent_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE lab.machines
            ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'idle'
                CHECK (status IN ('idle', 'running', 'broken', 'offline')),
            ADD COLUMN current_user_id INTEGER REFERENCES auth.users(id),
            ADD COLUMN status_note TEXT,
            ADD COLUMN status_updated_at TIMESTAMP NOT NULL DEFAULT NOW();

        INSERT INTO auth.role_permissions (role_name, permission_name)
        VALUES ('staff', 'lab.machine:manage')
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM auth.role_permissions
        WHERE role_name = 'staff' AND permission_name = 'lab.machine:manage';

        ALTER TABLE lab.machines
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS current_user_id,
            DROP COLUMN IF EXISTS status_note,
            DROP COLUMN IF EXISTS status_updated_at;
        """
    )
