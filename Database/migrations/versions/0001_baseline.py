"""baseline schema (mirrors the historical Database/init.sql, FK order fixed)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-26

"""
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE SCHEMA IF NOT EXISTS auth;

        CREATE TABLE auth.users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            full_name VARCHAR(128),
            email VARCHAR(128) UNIQUE,
            role VARCHAR(32) NOT NULL DEFAULT 'member',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE auth.rfid_cards (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES auth.users(id),
            card_uid VARCHAR(64) UNIQUE NOT NULL,
            valid_from TIMESTAMP,
            valid_to TIMESTAMP,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            added_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE auth.sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES auth.users(id),
            entry_time TIMESTAMP NOT NULL DEFAULT NOW(),
            exit_time TIMESTAMP,
            entry_reader VARCHAR(64),
            exit_reader VARCHAR(64),
            active BOOLEAN NOT NULL DEFAULT TRUE
        );

        CREATE TABLE auth.permissions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES auth.users(id),
            resource_type VARCHAR(64),
            resource_id VARCHAR(64),
            permission VARCHAR(64),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE SCHEMA IF NOT EXISTS inventory;

        CREATE TABLE inventory.materials (
            id SERIAL PRIMARY KEY,
            name VARCHAR(128),
            category VARCHAR(64),
            unit VARCHAR(16),
            sku VARCHAR(64),
            reorder_level NUMERIC,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE inventory.stock (
            id SERIAL PRIMARY KEY,
            material_id INTEGER REFERENCES inventory.materials(id),
            location VARCHAR(128),
            quantity NUMERIC NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE SCHEMA IF NOT EXISTS lab;

        CREATE TABLE lab.machines (
            id SERIAL PRIMARY KEY,
            name VARCHAR(128) NOT NULL,
            type VARCHAR(64) NOT NULL,
            location VARCHAR(128),
            capabilities JSONB,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE lab.machine_jobs (
            id SERIAL PRIMARY KEY,
            machine_id INTEGER REFERENCES lab.machines(id),
            user_id INTEGER REFERENCES auth.users(id),
            started_at TIMESTAMP NOT NULL,
            finished_at TIMESTAMP,
            status VARCHAR(32) NOT NULL,
            material_id INTEGER REFERENCES inventory.materials(id),
            material_qty NUMERIC,
            data_json JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE lab.reservations (
            id SERIAL PRIMARY KEY,
            machine_id INTEGER REFERENCES lab.machines(id),
            user_id INTEGER REFERENCES auth.users(id),
            reserved_from TIMESTAMP NOT NULL,
            reserved_to TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE SCHEMA IF NOT EXISTS orders;

        CREATE TABLE orders.vendors (
            id SERIAL PRIMARY KEY,
            name VARCHAR(128) NOT NULL,
            contact VARCHAR(256),
            address TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE orders.orders (
            id SERIAL PRIMARY KEY,
            vendor_id INTEGER REFERENCES orders.vendors(id),
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            created_by INTEGER REFERENCES auth.users(id),
            approved_by INTEGER REFERENCES auth.users(id),
            created_at TIMESTAMP DEFAULT NOW(),
            approved_at TIMESTAMP
        );

        CREATE TABLE orders.order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders.orders(id),
            material_id INTEGER REFERENCES inventory.materials(id),
            quantity NUMERIC NOT NULL,
            price NUMERIC,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE SCHEMA IF NOT EXISTS events;

        CREATE TABLE events.logs (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(64),
            user_id INTEGER REFERENCES auth.users(id),
            machine_id INTEGER REFERENCES lab.machines(id),
            message TEXT,
            data_json JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE SCHEMA IF NOT EXISTS internal;

        CREATE TABLE internal.students (
            student_id SERIAL PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            registration_date DATE NOT NULL DEFAULT CURRENT_DATE
        );

        CREATE TABLE internal.open_hours (
            id SERIAL PRIMARY KEY,
            weekday VARCHAR(16) NOT NULL,
            date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            capacity INT NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        -- lesson_hours must exist before excused (FK) — the original
        -- Database/init.sql had these reversed, which failed on a clean DB.
        CREATE TABLE internal.lesson_hours (
            lesson_id SERIAL PRIMARY KEY,
            weekday VARCHAR(16) NOT NULL,
            date DATE NOT NULL,
            class_name VARCHAR(50) NOT NULL,
            subject_name VARCHAR(100) NOT NULL,
            teacher_name VARCHAR(100) NOT NULL,
            hour_number INT NOT NULL CHECK (hour_number BETWEEN 0 AND 12)
        );

        CREATE TABLE internal.excused (
            excuse_id SERIAL PRIMARY KEY,
            student_id INT NOT NULL,
            lesson_id INT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES internal.students(student_id),
            FOREIGN KEY (lesson_id) REFERENCES internal.lesson_hours(lesson_id)
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP SCHEMA IF EXISTS internal CASCADE;
        DROP SCHEMA IF EXISTS events CASCADE;
        DROP SCHEMA IF EXISTS orders CASCADE;
        DROP SCHEMA IF EXISTS lab CASCADE;
        DROP SCHEMA IF EXISTS inventory CASCADE;
        DROP SCHEMA IF EXISTS auth CASCADE;
        """
    )
