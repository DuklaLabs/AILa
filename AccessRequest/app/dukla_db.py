"""Read-only access to the separate "duklamaps" timetable database.

This is a *different* Postgres server than the shared AILa `agentdb`
(`ailacore.db.get_pool`). It holds a scraped Bakaláři timetable with a
normalised schema:

    public.timetable_actual     – current week   (week_date = Monday)
    public.timetable_next       – next week
    public.timetable_permanent  – recurring timetable (no week_date)

    columns of interest: week_date, entity_type, day_index, hour_index,
                         teacher_name, subject_name/subject_abbrev,
                         class_abbrev, room_abbrev, change_type

The admin open-hours grid uses it to show which periods a supervising
teacher is already blocked by their own lesson, so a free hour can be
planned around it.

Everything here is best-effort: if the DB is not configured or is
unreachable, `fetch_supervisions` returns `[]` and the grid still works.
Use `diagnose()` (GET /api/open-hours/supervisions/debug) to see why it is
empty and to look up the exact `teacher_name` spelling.
"""
import os
import time
from datetime import date, timedelta
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None
_last_error: Optional[str] = None
_retry_after = 0.0  # unix ts; don't hammer create_pool while the DB is down

# day_index value that means Monday (Bakaláři scrapers vary: 0- or 1-based)
_DAY_BASE = int(os.getenv("DUKLA_DAY_BASE", "0"))

# academic-title tokens to ignore when matching "Bc. Jan Petrášek" against
# the timetable's "Petrášek Jan" style names
_TITLE_TOKENS = {
    "bc", "mgr", "ing", "mudr", "mvdr", "phdr", "rndr", "judr", "paeddr",
    "dis", "prof", "doc", "csc", "drsc", "ph", "d", "dr", "th", "mba",
}
_REMOVED_CHANGE_TYPES = {"cancelled", "canceled", "removed", "zrušeno", "odpadá"}


def _enabled() -> bool:
    return bool(os.getenv("DUKLA_PG_HOST", "").strip())


def _supervisor_names() -> list[str]:
    raw = os.getenv("DUKLA_SUPERVISORS", "")
    return [name.strip() for name in raw.split(",") if name.strip()]


def supervisor_names() -> list[str]:
    """Public: the configured supervisor display names, in order — used by
    the frontend to build the per-supervisor filter toggle."""
    return _supervisor_names()


def _name_tokens(name: str) -> list[str]:
    """Lower-cased name parts with titles/initials dropped, so word order
    and titles don't matter when matching."""
    out: list[str] = []
    for raw in name.replace(",", " ").split():
        tok = raw.strip(".").lower()
        if not tok or "." in raw or tok in _TITLE_TOKENS or len(tok) < 2:
            continue
        out.append(tok)
    return out


def _match_supervisors(db_teacher_name: str) -> list[str]:
    """Which configured supervisor display name(s) a timetable row's
    teacher_name belongs to (all tokens present, any order)."""
    hay = (db_teacher_name or "").lower()
    matched = []
    for name in _supervisor_names():
        toks = _name_tokens(name)
        if toks and all(t in hay for t in toks):
            matched.append(name)
    return matched


def _conn_kwargs() -> dict:
    return {
        "host": os.getenv("DUKLA_PG_HOST", "").strip(),
        "port": int(os.getenv("DUKLA_PG_PORT", "5432")),
        "database": os.getenv("DUKLA_PG_DB", "").strip(),
        "user": os.getenv("DUKLA_PG_USER", "").strip(),
        "password": os.getenv("DUKLA_PG_PASSWORD", ""),
    }


async def get_dukla_pool() -> Optional[asyncpg.Pool]:
    """Lazily create the pool. Returns None if disabled or a recent connect
    attempt failed (retried after a short cooldown, so fixed config
    recovers without restarting the process)."""
    global _pool, _last_error, _retry_after
    if not _enabled():
        _last_error = "DUKLA_PG_HOST není nastavené (propis dozorů je vypnutý)."
        return None
    if _pool is not None:
        return _pool
    if time.monotonic() < _retry_after:
        return None
    try:
        _pool = await asyncpg.create_pool(
            **_conn_kwargs(), min_size=0, max_size=4, command_timeout=5, timeout=5
        )
        _last_error = None
        return _pool
    except Exception as e:  # noqa: BLE001 - best effort, never crash the app
        _last_error = f"{type(e).__name__}: {e}"
        _retry_after = time.monotonic() + 60
        print("[dukla] pool init failed:", _last_error)
        return None


async def close_dukla_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _supervisor_where(start_param: int) -> tuple[str, list[list[str]]]:
    """SQL fragment matching teacher_name against every configured
    supervisor (all name tokens must be present, any order). Returns the
    fragment plus the token-list params it expects, bound at $start_param…"""
    token_lists = [t for t in (_name_tokens(n) for n in _supervisor_names()) if t]
    if not token_lists:
        return "FALSE", []
    clauses = []
    for i in range(len(token_lists)):
        p = start_param + i
        clauses.append(
            f"NOT EXISTS (SELECT 1 FROM unnest(${p}::text[]) tok "
            f"WHERE lower(teacher_name) NOT LIKE '%' || lower(tok) || '%')"
        )
    return "(" + " OR ".join(clauses) + ")", token_lists


_SELECT_COLS = (
    "day_index, hour_index, teacher_name, subject_name, subject_abbrev, "
    "class_abbrev, room_abbrev, change_type"
)


async def fetch_supervisions(
    monday: date, friday: date, week: str = "actual"
) -> list[dict]:
    """Lessons the configured supervising teacher(s) have in the given week
    (Mon–Fri), as [{date, hour_number, teacher_name, subject, class, room}].

    `week` picks the source table by its real `week_date` (the Monday):
    "next" -> timetable_next, else timetable_actual. No fallback to the
    permanent timetable — if that week genuinely has no teaching (holiday
    week), the result is empty. Set DUKLA_PERMANENT_FALLBACK=1 to fall back
    to timetable_permanent when the week table is empty. Best-effort: any
    failure -> []."""
    global _last_error

    if not _supervisor_names():
        _last_error = "DUKLA_SUPERVISORS je prázdné (žádná jména dozorů)."
        return []

    pool = await get_dukla_pool()
    if pool is None:
        return []

    week_table = "public.timetable_next" if week == "next" else "public.timetable_actual"
    sup_sql, token_lists = _supervisor_where(2)          # $1 = monday, $2.. = tokens
    sup_sql_p1, _ = _supervisor_where(1)                 # permanent: no $1

    week_q = (
        f"SELECT {_SELECT_COLS} FROM {week_table} "
        f"WHERE entity_type = 'teachers' AND week_date = $1 AND {sup_sql}"
    )
    perm_q = (  # timetable_permanent has no week_date / change_type
        "SELECT day_index, hour_index, teacher_name, subject_name, subject_abbrev, "
        "class_abbrev, room_abbrev, NULL::text AS change_type "
        "FROM public.timetable_permanent "
        f"WHERE entity_type = 'teachers' AND {sup_sql_p1}"
    )
    allow_perm = os.getenv("DUKLA_PERMANENT_FALLBACK", "").strip() in ("1", "true", "yes")

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(week_q, monday, *token_lists)
            if not rows and allow_perm:
                rows = await conn.fetch(perm_q, *token_lists)
        _last_error = None
    except Exception as e:  # noqa: BLE001 - best effort
        _last_error = f"{type(e).__name__}: {e}"
        print("[dukla] fetch_supervisions failed:", _last_error)
        return []

    seen: set[tuple] = set()
    out: list[dict] = []
    for r in rows:
        if str(r["change_type"] or "").strip().lower() in _REMOVED_CHANGE_TYPES:
            continue
        offset = r["day_index"] - _DAY_BASE
        if offset < 0 or offset > 4:
            continue
        day = (monday + timedelta(days=offset)).isoformat()
        hour = r["hour_index"]
        subject = r["subject_name"] or r["subject_abbrev"] or ""
        # one block per configured supervisor this row belongs to
        for supervisor in _match_supervisors(r["teacher_name"]) or [r["teacher_name"]]:
            key = (supervisor, day, hour, subject, r["class_abbrev"])
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "supervisor": supervisor,
                    "date": day,
                    "hour_number": hour,
                    "teacher_name": r["teacher_name"],
                    "subject_name": subject,
                    "class_name": r["class_abbrev"] or "",
                    "room": r["room_abbrev"] or "",
                }
            )
    return out


async def blocked_supervisors(day: date, hour_number: int) -> set[str]:
    """Configured supervisors who already have their own lesson at
    day+hour in the duklamaps timetable — they must not also be assigned
    as a free-hour dozor at that time. Empty set if duklamaps can't be
    reached (can't verify -> don't block planning)."""
    monday = day - timedelta(days=day.weekday())
    today = date.today()
    today_monday = today - timedelta(days=today.weekday())
    week = "next" if monday > today_monday else "actual"
    rows = await fetch_supervisions(monday, monday + timedelta(days=4), week)
    iso = day.isoformat()
    return {
        r["supervisor"]
        for r in rows
        if r["date"] == iso and r["hour_number"] == hour_number
    }


async def diagnose() -> dict:
    """Connection + data status, surfaced at
    GET /api/open-hours/supervisions/debug."""
    kw = _conn_kwargs()
    sup = _supervisor_names()
    info: dict = {
        "enabled": _enabled(),
        "config": {
            "host": kw["host"], "port": kw["port"], "database": kw["database"],
            "user": kw["user"], "day_base": _DAY_BASE,
            "supervisors": sup,
            "supervisor_tokens": [_name_tokens(n) for n in sup],
        },
        "connected": False,
        "table_counts": {},
        "supervisor_matches": {},
        "teacher_name_samples": [],
        "last_fetch_error": _last_error,
        "error": None,
    }
    if not _enabled():
        info["error"] = "DUKLA_PG_HOST není nastavené."
        return info

    try:
        pool = await asyncpg.create_pool(
            **kw, min_size=0, max_size=1, command_timeout=5, timeout=5
        )
    except Exception as e:  # noqa: BLE001
        info["error"] = f"Připojení selhalo: {type(e).__name__}: {e}"
        return info

    try:
        async with pool.acquire() as conn:
            info["connected"] = True
            for t in ("public.timetable_actual", "public.timetable_next",
                      "public.timetable_permanent"):
                try:
                    info["table_counts"][t] = await conn.fetchval(
                        f"SELECT COUNT(*) FROM {t} WHERE entity_type = 'teachers'"
                    )
                except Exception as e:  # noqa: BLE001
                    info["table_counts"][t] = f"err: {e}"

            for src, name in zip(sup, [_name_tokens(n) for n in sup]):
                if not name:
                    info["supervisor_matches"][src] = "žádné použitelné tokeny"
                    continue
                try:
                    n = await conn.fetchval(
                        "SELECT COUNT(*) FROM ("
                        "  SELECT teacher_name FROM public.timetable_next "
                        "  WHERE entity_type='teachers' "
                        "  UNION ALL "
                        "  SELECT teacher_name FROM public.timetable_permanent "
                        "  WHERE entity_type='teachers'"
                        ") x WHERE NOT EXISTS ("
                        "  SELECT 1 FROM unnest($1::text[]) tok "
                        "  WHERE lower(teacher_name) NOT LIKE '%'||lower(tok)||'%')",
                        name,
                    )
                    info["supervisor_matches"][src] = n
                except Exception as e:  # noqa: BLE001
                    info["supervisor_matches"][src] = f"err: {e}"

            try:
                srows = await conn.fetch(
                    "SELECT DISTINCT teacher_name FROM public.timetable_permanent "
                    "WHERE entity_type='teachers' AND teacher_name <> '' "
                    "ORDER BY 1 LIMIT 300"
                )
                info["teacher_name_samples"] = [r["teacher_name"] for r in srows]
            except Exception as e:  # noqa: BLE001
                info["error"] = f"teacher sample: {e}"
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    finally:
        await pool.close()
    return info
