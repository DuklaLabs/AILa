"""Naseeduje demo data pro vyzkoušení procesu povolování uvolnění z výuky.

    docker compose exec access-request-server python -m app.seed_demo

Vytvoří pár studentů (s funkčním loginem) s **reálnými třídami z rozvrhu**,
několik otevřených hodin DuklaLabs (dozor "Bc. Jan Petrášek") a zápisy studentů
na ně. Termíny hodin se vybírají tak, aby se většina zápisů napojila na
skutečného učitele podle rozvrhu (duklamaps) a aspoň jeden spadl na fallback
dozora (hodina bez výuky).

Student má e-mail honzapetrasekb+dl.<jméno>@gmail.com. Kvůli
`MAIL_REDIRECT_TO=petrasek@spssecb.cz` v Messengeru fakticky přijdou všechny
notifikace na petrasek@spssecb.cz.

Skript je idempotentní: nejdřív smaže svá dřívější demo data.
"""
from __future__ import annotations

import asyncio
import datetime
import secrets

from ailacore.auth import hash_password
from ailacore.db import close_pool, get_pool

from app import dukla_db
from app.open_hours import _PERIODS_BY_NUMBER

DEMO_TAG = "DEMO – "
STUDENT_PASSWORD = "duklalabs"
SUPERVISOR = "Bc. Jan Petrášek"

# (jméno, příjmení, e-mail, třída z rozvrhu)
STUDENTS = [
    ("Anna", "Nováková", "honzapetrasekb+dl.anna@gmail.com", "4.ER"),
    ("Petr", "Dvořák", "honzapetrasekb+dl.petr@gmail.com", "2.EM"),
    ("Eva", "Kučerová", "honzapetrasekb+dl.eva@gmail.com", "1.ER"),
    ("Tomáš", "Marek", "honzapetrasekb+dl.tomas@gmail.com", "4.ER"),
]

CANDIDATE_CLASSES = ["4.ER", "2.EM", "1.ER"]
CANDIDATE_HOURS = [1, 2, 3, 4, 5]


async def _pick_slots(target_day: datetime.date):
    """Vrátí (resolving_slots, fallback_slot) pro daný den.
    resolving_slots = [(hour, [teacher_name,...])], fallback_slot = hour bez výuky."""
    resolving: list[tuple[int, list[str]]] = []
    fallback: int | None = None
    for hour in CANDIDATE_HOURS:
        any_teacher = False
        for cls in CANDIDATE_CLASSES:
            ts = await dukla_db.class_teachers(cls, target_day, hour)
            if ts:
                any_teacher = True
                if len(resolving) < 3:
                    resolving.append((hour, [t["teacher_name"] for t in ts]))
                break
        if not any_teacher and fallback is None:
            fallback = hour
    return resolving, fallback


async def main() -> None:
    pool = await get_pool()
    emails = [s[2] for s in STUDENTS]

    today = datetime.date.today()
    target_day = today + datetime.timedelta(days=(7 - today.weekday()))  # příští pondělí
    resolving, fallback = await _pick_slots(target_day)
    if fallback is None:
        fallback = 0  # nultá hodina bývá volná

    # Otevřené hodiny: rozvrhové sloty + jeden fallback (bez učitele).
    hours_spec: list[tuple[int, str]] = [
        (h, DEMO_TAG + f"rozvrh {h}. h ({', '.join(tn)})") for h, tn in resolving
    ]
    hours_spec.append((fallback, DEMO_TAG + f"fallback {fallback}. h (bez výuky → dozor)"))

    async with pool.acquire() as conn:
        async with conn.transaction():
            # --- úklid ---
            await conn.execute(
                "DELETE FROM internal.bookings b USING internal.open_hours oh "
                "WHERE b.open_hour_id = oh.id AND oh.note LIKE $1", DEMO_TAG + "%")
            await conn.execute(
                "DELETE FROM internal.bookings WHERE student_id IN "
                "(SELECT student_id FROM internal.students WHERE email = ANY($1::text[]))",
                emails)
            await conn.execute(
                "DELETE FROM auth.web_sessions WHERE user_id IN "
                "(SELECT id FROM auth.users WHERE username = ANY($1::text[]))", emails)
            await conn.execute(
                "DELETE FROM internal.students WHERE email = ANY($1::text[])", emails)
            await conn.execute(
                "DELETE FROM auth.users WHERE username = ANY($1::text[])", emails)
            await conn.execute(
                "DELETE FROM internal.open_hours WHERE note LIKE $1", DEMO_TAG + "%")

            # --- studenti ---
            ph = hash_password(STUDENT_PASSWORD)
            student_ids: list[int] = []
            for fn, ln, em, cg in STUDENTS:
                uid = await conn.fetchval(
                    "INSERT INTO auth.users "
                    "(username, full_name, email, role, password_hash, is_active) "
                    "VALUES ($1,$2,$3,'student',$4,TRUE) RETURNING id",
                    em, f"{fn} {ln}", em, ph)
                sid = await conn.fetchval(
                    "INSERT INTO internal.students "
                    "(first_name,last_name,email,class_group,user_id,release_token) "
                    "VALUES ($1,$2,$3,$4,$5,$6) RETURNING student_id",
                    fn, ln, em, cg, uid, secrets.token_urlsafe(24))
                student_ids.append(sid)

            # 1. a 2. student mají uvolňování schválené (třídní + koordinátor),
            # 3. a 4. čekají → ukáže se to v adminu i v mřížce.
            await conn.execute(
                "UPDATE internal.students SET release_teacher_ok=TRUE, "
                "release_coord_ok=TRUE WHERE student_id = ANY($1::int[])",
                student_ids[:2])

            # --- otevřené hodiny ---
            hour_ids: list[int] = []
            for hn, note in hours_spec:
                st, en = _PERIODS_BY_NUMBER[hn]
                hid = await conn.fetchval(
                    "INSERT INTO internal.open_hours "
                    "(weekday, date, hour_number, start_time, end_time, capacity, "
                    " note, supervisor) "
                    "VALUES (trim(to_char($1::date, 'Day')), $1::date, $2, $3, $4, 6, $5, $6) "
                    "ON CONFLICT (date, hour_number) DO UPDATE SET "
                    "  start_time=EXCLUDED.start_time, end_time=EXCLUDED.end_time, "
                    "  capacity=EXCLUDED.capacity, note=EXCLUDED.note, "
                    "  supervisor=EXCLUDED.supervisor RETURNING id",
                    target_day, hn, st, en, note, SUPERVISOR)
                hour_ids.append(hid)

            # --- zápisy: každý student do 1–2 hodin ---
            plan = [
                (0, [0, 1, 2]),
                (1, [0, 3]) if len(hour_ids) > 1 else (0, []),
                (len(hour_ids) - 1, [1, 3]),  # poslední = fallback slot
            ]
            n_bookings = 0
            for hi, sidx in plan:
                for si in sidx:
                    await conn.execute(
                        "INSERT INTO internal.bookings "
                        "(student_id, open_hour_id, decision_token) VALUES ($1,$2,$3) "
                        "ON CONFLICT (student_id, open_hour_id) DO NOTHING",
                        student_ids[si], hour_ids[hi], secrets.token_urlsafe(24))
                    n_bookings += 1

    print(f"Seed OK: {len(STUDENTS)} studentů, {len(hour_ids)} hodin na {target_day}, "
          f"{n_bookings} zápisů.")
    for hn, note in hours_spec:
        print(f"  - {hn}. h: {note}")
    print(f"Login studentů: uživatel = e-mail, heslo = {STUDENT_PASSWORD!r}")
    print("Dál: /admin → 'Rozeslat učitelům (žádosti)' / 'Rozeslat dozorům (docházka)'")
    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
