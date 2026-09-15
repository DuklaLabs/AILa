"""sloučení dvou souběžných větví, co obě navazují na 0016_projects.

`0008_lesson_hours_dedup` -> `0009_excuse_workflow` (omluvenkový workflow) a
`0017_agent_layer` (agentní vrstva §21) vznikly nezávisle na sobě jako dvě
samostatné větve za `0016_projects` – žádná neexistovala, když druhá
vznikala. Bez tohohle merge by `alembic upgrade head` na čerstvé DB spadl na
"Multiple head revisions" (viz Database/README.md, sekce o pořadí migrací).
Prázdná migrace, jen spojuje historii.

Revision ID: 0018_merge_heads
Revises: 0009_excuse_workflow, 0017_agent_layer
Create Date: 2026-09-15

"""

revision = "0018_merge_heads"
down_revision = ("0009_excuse_workflow", "0017_agent_layer")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
