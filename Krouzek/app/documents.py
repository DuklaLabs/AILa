"""Obecný JSON document store pro Kroužek (ZŠ/SŠ klub, port samostatného
prototypu).

Prototyp držel svoje kolekce (žáci, schůzky, projekty, kontakty, nastavení,
...) v localStorage jako volné JS objekty, jejichž tvar se ještě bude měnit
a mezi kolekcemi nejsou FK vztahy ani průřezové dotazy. Místo vlastních
tabulek pro každou kolekci je tu jedna obecná `club.documents(collection,
id, data jsonb)` tabulka a tenhle router nad ní dělá CRUD + historii/undo
zdroj (`club.history`), který prototyp taky měl. Jméno kolekce je libovolný
string z klienta — validuje se jen regexem proti zneužití, nikdy se
neinterpoluje do SQL (vždy jako parametr).
"""
import json
import re
import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from ailacore.auth import get_current_user, require_role
from ailacore.db import get_pool
from ailacore.models import User

router = APIRouter(prefix="/api/club", tags=["club"])

_COLLECTION_RE = re.compile(r"^[a-zA-Z0-9_]{1,64}$")


def _check_collection(collection: str) -> str:
    if not _COLLECTION_RE.match(collection):
        raise HTTPException(status_code=400, detail="Invalid collection name")
    return collection


def _jsonb(value):
    """asyncpg nemá globálně zaregistrovaný jsonb kodek (stejná konvence jako
    ailacore.admin._jsonb) – čtený jsonb sloupec přijde jako str, potřebuje
    json.loads. None (NULL) zůstává None."""
    if value is None:
        return None
    return json.loads(value) if isinstance(value, str) else value


def _dump(data: Optional[dict]) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False, default=str)


async def _record_history(conn, collection: str, doc_id: str, op: str, before: Optional[dict]) -> None:
    await conn.execute(
        """
        INSERT INTO club.history (at, path, op, before, label)
        VALUES ($1, $2, $3, $4::jsonb, $5)
        """,
        int(time.time() * 1000),
        f"{collection}/{doc_id}",
        op,
        _dump(before) if before is not None else None,
        f"{op} {collection}/{doc_id}",
    )


@router.get("/history")
async def list_history(limit: int = 150, user: User = Depends(get_current_user)):
    """Čtení historie = kdokoliv přihlášený, stejně jako čtení dokumentů."""
    limit = max(1, min(limit, 1000))
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, at, path, op, before, label, undone
            FROM club.history
            ORDER BY at DESC
            LIMIT $1
            """,
            limit,
        )
    return [{**dict(row), "before": _jsonb(row["before"])} for row in rows]


@router.get("/{collection}")
async def list_documents(collection: str = Path(...), user: User = Depends(get_current_user)):
    _check_collection(collection)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, data FROM club.documents WHERE collection = $1",
            collection,
        )
    return [{"id": row["id"], **_jsonb(row["data"])} for row in rows]


@router.put("/{collection}/{doc_id}")
async def set_document(
    collection: str,
    doc_id: str,
    data: dict[str, Any],
    user: User = Depends(require_role("admin", "staff")),
):
    _check_collection(collection)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            prev = await conn.fetchrow(
                "SELECT data FROM club.documents WHERE collection = $1 AND id = $2",
                collection,
                doc_id,
            )
            await conn.execute(
                """
                INSERT INTO club.documents (collection, id, data, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (collection, id) DO UPDATE SET data = $3::jsonb, updated_at = now()
                """,
                collection,
                doc_id,
                _dump(data),
            )
            await _record_history(conn, collection, doc_id, "set", _jsonb(prev["data"]) if prev else None)
    return {"id": doc_id, **data}


@router.patch("/{collection}/{doc_id}")
async def update_document(
    collection: str,
    doc_id: str,
    patch: dict[str, Any],
    user: User = Depends(require_role("admin", "staff")),
):
    _check_collection(collection)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            prev = await conn.fetchrow(
                "SELECT data FROM club.documents WHERE collection = $1 AND id = $2",
                collection,
                doc_id,
            )
            before = _jsonb(prev["data"]) if prev else None
            merged = {**(before or {}), **patch}
            await conn.execute(
                """
                INSERT INTO club.documents (collection, id, data, updated_at)
                VALUES ($1, $2, $3::jsonb, now())
                ON CONFLICT (collection, id) DO UPDATE SET data = $3::jsonb, updated_at = now()
                """,
                collection,
                doc_id,
                _dump(merged),
            )
            await _record_history(conn, collection, doc_id, "update", before)
    return {"id": doc_id, **merged}


@router.delete("/{collection}/{doc_id}", status_code=204)
async def delete_document(
    collection: str,
    doc_id: str,
    user: User = Depends(require_role("admin", "staff")),
):
    _check_collection(collection)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            prev = await conn.fetchrow(
                "SELECT data FROM club.documents WHERE collection = $1 AND id = $2",
                collection,
                doc_id,
            )
            if prev is not None:
                await conn.execute(
                    "DELETE FROM club.documents WHERE collection = $1 AND id = $2",
                    collection,
                    doc_id,
                )
                await _record_history(conn, collection, doc_id, "delete", _jsonb(prev["data"]))
    # idempotentní: smazání neexistujícího dokumentu taky vrátí 204


class BatchOp(BaseModel):
    op: Literal["set", "update", "delete"]
    collection: str
    id: str
    data: Optional[dict[str, Any]] = None


class BatchRequest(BaseModel):
    ops: list[BatchOp]


@router.post("/batch")
async def batch(payload: BatchRequest, user: User = Depends(require_role("admin", "staff"))):
    """Obnova ze zálohy / hromadná úprava — všechny operace v jedné
    transakci, stejná sémantika jako jednotlivé endpointy výše."""
    pool = await get_pool()
    applied = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            for item in payload.ops:
                collection = _check_collection(item.collection)
                prev = await conn.fetchrow(
                    "SELECT data FROM club.documents WHERE collection = $1 AND id = $2",
                    collection,
                    item.id,
                )
                before = _jsonb(prev["data"]) if prev else None

                if item.op == "delete":
                    if prev is not None:
                        await conn.execute(
                            "DELETE FROM club.documents WHERE collection = $1 AND id = $2",
                            collection,
                            item.id,
                        )
                        await _record_history(conn, collection, item.id, "delete", before)
                else:
                    new_data = item.data or {}
                    if item.op == "update":
                        new_data = {**(before or {}), **new_data}
                    await conn.execute(
                        """
                        INSERT INTO club.documents (collection, id, data, updated_at)
                        VALUES ($1, $2, $3::jsonb, now())
                        ON CONFLICT (collection, id) DO UPDATE SET data = $3::jsonb, updated_at = now()
                        """,
                        collection,
                        item.id,
                        _dump(new_data),
                    )
                    await _record_history(conn, collection, item.id, item.op, before)
                applied += 1
    return {"applied": applied}
