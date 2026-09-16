"""SQLite connection and schema setup.

SQLite is used because it is included with Python, costs nothing, and keeps the
entire MVP portable. Each helper opens a short-lived connection so a failed web
request cannot leave a transaction hanging.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("MENSANA_DB", "data/mensana.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
 id INTEGER PRIMARY KEY AUTOINCREMENT, legal_name TEXT NOT NULL,
 normalized_name TEXT NOT NULL, country TEXT NOT NULL CHECK(country IN ('CA','US')),
 industry TEXT NOT NULL DEFAULT 'Unknown', website TEXT, normalized_domain TEXT,
 phone TEXT, phone_type TEXT, phone_source TEXT, phone_verified_at TEXT,
 contact_name TEXT, contact_role TEXT, email TEXT, ticker TEXT, cik TEXT,
 employee_count INTEGER, revenue REAL, source_url TEXT,
 status TEXT NOT NULL DEFAULT 'NEW', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(country, normalized_name)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_cik ON companies(cik) WHERE cik IS NOT NULL AND cik <> '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_domain ON companies(normalized_domain) WHERE normalized_domain IS NOT NULL AND normalized_domain <> '';
CREATE TABLE IF NOT EXISTS features (
 company_id INTEGER PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
 revenue_growth REAL DEFAULT 0, margin_change REAL DEFAULT 0, expense_growth REAL DEFAULT 0,
 recent_acquisition INTEGER DEFAULT 0, restructuring INTEGER DEFAULT 0,
 management_change INTEGER DEFAULT 0, efficiency_mentions INTEGER DEFAULT 0,
 cost_mentions INTEGER DEFAULT 0, financial_score REAL DEFAULT 0,
 operational_score REAL DEFAULT 0, transformation_score REAL DEFAULT 0,
 nlp_score REAL DEFAULT 0, fit_score REAL DEFAULT 0, heuristic_score REAL DEFAULT 0,
 model_probability REAL, final_score REAL DEFAULT 0, calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS signals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
 category TEXT NOT NULL, label TEXT NOT NULL, points REAL NOT NULL, evidence TEXT NOT NULL,
 source_url TEXT, observed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS calls (
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL REFERENCES companies(id),
 called_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reached TEXT NOT NULL,
 opportunity TEXT NOT NULL CHECK(opportunity IN ('YES','NO','UNSURE','UNKNOWN')),
 opportunity_type TEXT, strength TEXT, meeting INTEGER DEFAULT 0,
 follow_up_at TEXT, notes TEXT, phone_used TEXT,
 do_not_contact INTEGER DEFAULT 0,
 voided_at TEXT,
 void_reason TEXT
);
CREATE TABLE IF NOT EXISTS model_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, trained_at TEXT DEFAULT CURRENT_TIMESTAMP,
 label_count INTEGER NOT NULL, positive_count INTEGER NOT NULL, accuracy REAL,
 accepted INTEGER NOT NULL, notes TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 action TEXT NOT NULL, company_id INTEGER, details TEXT
);
"""

def init_db() -> None:
    """Create the data directory and every table if this is the first run."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(SCHEMA)
        # Existing V0.1 databases need these columns added without deleting any
        # companies, calls, or training feedback. SQLite has no IF NOT EXISTS
        # option for ADD COLUMN, so inspect the table before each migration.
        call_columns = {row[1] for row in connection.execute("PRAGMA table_info(calls)")}
        migrations = {
            "do_not_contact": "ALTER TABLE calls ADD COLUMN do_not_contact INTEGER DEFAULT 0",
            "voided_at": "ALTER TABLE calls ADD COLUMN voided_at TEXT",
            "void_reason": "ALTER TABLE calls ADD COLUMN void_reason TEXT",
        }
        for column, statement in migrations.items():
            if column not in call_columns:
                connection.execute(statement)
        connection.execute("PRAGMA journal_mode=WAL")

@contextmanager
def db():
    """Yield a dictionary-like database connection and commit safely."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
