"""Weekly per-teacher digest of pending excuse requests — run by an
APScheduler cron job wired up in main.py (Thursdays 12:00)."""
import logging
import secrets

from ailacore.db import get_pool

from app.mailer import render_email, send_email

log = logging.getLogger(__name__)


async def run_weekly_digest() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT er.id, er.teacher_id, er.teacher_email, er.token,
                   s.first_name, s.last_name, s.class_group,
                   lh.date, lh.hour_number, lh.subject_name
            FROM internal.excuse_requests er
            JOIN internal.students s ON s.student_id = er.student_id
            JOIN internal.lesson_hours lh ON lh.lesson_id = er.lesson_id
            WHERE er.status = 'pending'
            ORDER BY er.teacher_email, lh.date, lh.hour_number
            """
        )
        if not rows:
            log.info("Weekly excuse digest: nothing pending, no mail sent.")
            return

        by_teacher: dict[str, list[dict]] = {}
        for row in rows:
            by_teacher.setdefault(row["teacher_email"], []).append(dict(row))

        for teacher_email, items in by_teacher.items():
            batch_token = secrets.token_urlsafe(32)
            async with conn.transaction():
                batch_id = await conn.fetchval(
                    """
                    INSERT INTO internal.excuse_digest_batches (teacher_id, teacher_email, token)
                    VALUES ($1, $2, $3) RETURNING id
                    """,
                    items[0]["teacher_id"],
                    teacher_email,
                    batch_token,
                )
                await conn.executemany(
                    "INSERT INTO internal.excuse_digest_batch_items (batch_id, excuse_request_id) VALUES ($1, $2)",
                    [(batch_id, item["id"]) for item in items],
                )

            try:
                html = render_email("teacher_digest.html", items=items, batch_token=batch_token)
                await send_email(teacher_email, "Žádosti o uvolnění – DuklaLabs", html)
            except Exception:
                log.exception(
                    "Failed to send weekly excuse digest to %s (batch %s stays unsent, "
                    "requests remain pending for next week's run)",
                    teacher_email,
                    batch_id,
                )
                continue

            await conn.execute(
                "UPDATE internal.excuse_digest_batches SET sent_at = NOW() WHERE id = $1", batch_id
            )
            log.info("Sent weekly excuse digest to %s (%d requests)", teacher_email, len(items))
