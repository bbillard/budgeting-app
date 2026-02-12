from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount_original REAL NOT NULL,
    amount_effective REAL NOT NULL,
    category TEXT NOT NULL,
    category_original TEXT NOT NULL,
    is_excluded INTEGER NOT NULL DEFAULT 0,
    split_ratio REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_excluded ON transactions(is_excluded);
"""


def get_db_path() -> Path:
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "budget.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA_SQL)
