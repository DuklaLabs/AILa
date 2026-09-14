"""excuse-request approval workflow: replaces the old auto-approve in
_excuse_from_regular_lesson with a real pending/approved/denied flow.

- excuse_requests: one row per booking that collided with a real lesson,
  gated on a teacher's yes/no decision (via a token-based email link)
  instead of writing internal.excused immediately.
- excuse_digest_batches / excuse_digest_batch_items: the weekly digest
  emails one teacher one summary of everything pending, and "approve/deny
  all" must only ever apply to what was actually in that specific email —
  not to anything filed after it was sent — so each send snapshots its
  batch membership rather than re-querying "all pending" at click time.
- missing_teacher_tickets: when a lesson's teacher has no email on file in
  DuklaMaps, the booking is rejected outright (see bookings.py) and this
  records it for staff to resolve — deduplicated per teacher via upsert,
  not one row per failed attempt.
- internal.bookings gets a soft-cancel (cancelled_at/cancelled_reason)
  since a denied excuse now also cancels the booking, and there was no
  cancel mechanism before this. The old UNIQUE(student_id, open_hour_id)
  is replaced with a partial index over active bookings only, so a student
  whose booking got cancelled can book the same slot again.

Revision ID: 0009_excuse_workflow
Revises: 0008_lesson_hours_dedup
Create Date: 2026-08-27

"""
from alembic import op

revision = "0009_excuse_workflow"
down_revision = "0008_lesson_hours_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.bookings
            ADD COLUMN cancelled_at TIMESTAMP,
            ADD COLUMN cancelled_reason VARCHAR(32);

        ALTER TABLE internal.bookings
            DROP CONSTRAINT IF EXISTS bookings_student_id_open_hour_id_key;

        CREATE UNIQUE INDEX uq_bookings_active_slot
            ON internal.bookings (student_id, open_hour_id)
            WHERE cancelled_at IS NULL;

        CREATE TABLE internal.excuse_requests (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES internal.students(student_id),
            booking_id INTEGER NOT NULL UNIQUE REFERENCES internal.bookings(id),
            lesson_id INTEGER NOT NULL REFERENCES internal.lesson_hours(lesson_id),
            -- DuklaMaps is a separate DB (no cross-DB FK possible), so
            -- teacher_id/teacher_email are denormalized snapshots taken at
            -- booking time — same pattern internal.lesson_hours already
            -- uses for teacher_name.
            teacher_id VARCHAR(32) NOT NULL,
            teacher_email VARCHAR(256) NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'approved', 'denied')),
            token VARCHAR(128) UNIQUE NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            decided_at TIMESTAMP,
            decided_via VARCHAR(16) CHECK (decided_via IN ('individual', 'bulk'))
        );

        -- Guards against two simultaneously pending requests for the same
        -- student+lesson (e.g. duplicate open_hours rows for the same
        -- date/hour_number). A new pending request for the same pair is
        -- fine once the earlier one is decided.
        CREATE UNIQUE INDEX uq_excuse_requests_pending_lesson
            ON internal.excuse_requests (student_id, lesson_id)
            WHERE status = 'pending';

        CREATE INDEX idx_excuse_requests_status_email
            ON internal.excuse_requests (status, teacher_email);

        CREATE TABLE internal.excuse_digest_batches (
            id SERIAL PRIMARY KEY,
            teacher_id VARCHAR(32) NOT NULL,
            teacher_email VARCHAR(256) NOT NULL,
            token VARCHAR(128) UNIQUE NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            sent_at TIMESTAMP
        );

        CREATE TABLE internal.excuse_digest_batch_items (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER NOT NULL REFERENCES internal.excuse_digest_batches(id),
            excuse_request_id INTEGER NOT NULL REFERENCES internal.excuse_requests(id),
            UNIQUE (batch_id, excuse_request_id)
        );

        CREATE INDEX idx_excuse_digest_batch_items_batch_id
            ON internal.excuse_digest_batch_items (batch_id);

        CREATE TABLE internal.missing_teacher_tickets (
            id SERIAL PRIMARY KEY,
            teacher_id VARCHAR(32) NOT NULL UNIQUE,
            teacher_name VARCHAR(100),
            first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
            last_seen TIMESTAMP NOT NULL DEFAULT NOW(),
            attempts_count INTEGER NOT NULL DEFAULT 1,
            resolved BOOLEAN NOT NULL DEFAULT FALSE,
            resolved_at TIMESTAMP,
            resolved_by INTEGER REFERENCES auth.users(id)
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS internal.missing_teacher_tickets;
        DROP TABLE IF EXISTS internal.excuse_digest_batch_items;
        DROP TABLE IF EXISTS internal.excuse_digest_batches;
        DROP TABLE IF EXISTS internal.excuse_requests;

        DROP INDEX IF EXISTS internal.uq_bookings_active_slot;
        ALTER TABLE internal.bookings
            ADD CONSTRAINT bookings_student_id_open_hour_id_key UNIQUE (student_id, open_hour_id);
        ALTER TABLE internal.bookings
            DROP COLUMN IF EXISTS cancelled_reason,
            DROP COLUMN IF EXISTS cancelled_at;
        """
    )
