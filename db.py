from __future__ import annotations

import os
import sqlite3
from pathlib import Path


BASE_CATEGORIES = [
    "À catégoriser",
    "Logement",
    "Transport",
    "Alimentation",
    "Achats",
    "Loisirs",
    "Santé",
    "Famille",
    "Cadeaux",
    "Revenus",
    "Autres",
]


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

CREATE TABLE IF NOT EXISTS categories (
    name TEXT PRIMARY KEY,
    parent_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_name);
"""


def get_db_path() -> Path:
    override = os.getenv("BUDGET_DB_PATH")
    if override:
        path = Path(override)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

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
        now = "1970-01-01 00:00:00"
        for category in BASE_CATEGORIES:
            conn.execute(
                "INSERT OR IGNORE INTO categories (name, parent_name, created_at, updated_at) VALUES (?, NULL, ?, ?)",
                (category, now, now),
            )
