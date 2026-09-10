"""Fake asyncpg pool/conn pro testy agentů (bez DB)."""
from __future__ import annotations


class FakeConn:
    def __init__(self, rows: dict | None = None):
        self._rows = rows or {}
        self.audit: list[tuple] = []
        self.reports: list[dict] = []
        self.proposals: list[dict] = []

    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        return _Tx()

    async def execute(self, sql, *args):
        if "auth.audit_log" in sql:
            self.audit.append(args)
        return "INSERT 0 1"

    async def fetch(self, sql, *args):
        return self._rows.get("fetch", [])

    async def fetchval(self, sql, *args):
        return self._rows.get("fetchval", 0)

    async def fetchrow(self, sql, *args):
        if "INSERT INTO agent.proposals" in sql:
            (module, agent, kind, tt, tid, payload, summary, conf, status) = args
            row = dict(
                id=len(self.proposals) + 1, module=module, agent=agent, kind=kind,
                target_type=tt, target_id=tid, payload=payload, summary=summary,
                confidence=conf, status=status, created_at=None,
                reviewed_by_user_id=None, reviewed_at=None, review_note=None,
            )
            self.proposals.append(row)
            return row
        if "INSERT INTO agent.reports" in sql:
            module, period, payload, summary = args
            row = dict(id=1, module=module, period=period, payload=payload,
                       summary=summary, generated_at=None)
            self.reports.append(row)
            return row
        if sql.strip().startswith("SELECT payload, summary FROM agent.reports"):
            return self._rows.get("prev_report")
        return None


class FakePool:
    def __init__(self, conn: FakeConn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Acq:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        return _Acq()
