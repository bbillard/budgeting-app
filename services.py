from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from categorization import DEFAULT_CATEGORY, infer_category
from db import BASE_CATEGORIES, get_conn


DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
CATEGORIES = BASE_CATEGORIES


def now_str() -> str:
    return datetime.now().strftime(DATETIME_FMT)


def parse_amount(raw: str) -> float:
    cleaned = raw.replace("€", "").replace(" ", "").replace("\u202f", "").replace(",", ".")
    return float(cleaned)


def parse_date(raw: str) -> str:
    value = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Format de date non reconnu: {raw}")


def detect_column(headers: list[str], candidates: list[str]) -> str | None:
    lowered = {h.lower().strip(): h for h in headers}
    for candidate in candidates:
        key = candidate.lower().strip()
        if key in lowered:
            return lowered[key]
    return None


def detect_delimiter(decoded: str) -> str:
    first_line = decoded.splitlines()[0] if decoded.splitlines() else ""
    if first_line.count(";") >= first_line.count(","):
        return ";"
    return ","


def normalize_category(raw: str) -> str:
    value = (raw or "").strip()
    lowered = value.lower().replace("é", "e").replace("à", "a")
    if lowered in {"a categoriser", "à categoriser", "à catégoriser", "a catégoriser", ""}:
        return DEFAULT_CATEGORY
    return value


def split_category_levels(category: str) -> tuple[str, str | None]:
    if " / " in category:
        parent, child = category.split(" / ", 1)
        return parent.strip(), child.strip() or None
    return category.strip(), None


def ensure_category_exists(category: str, conn=None) -> None:
    category = normalize_category(category)
    parent, child = split_category_levels(category)

    owns_conn = conn is None
    if owns_conn:
        conn = get_conn()

    stamp = now_str()
    conn.execute(
        "INSERT OR IGNORE INTO categories (name, parent_name, created_at, updated_at) VALUES (?, NULL, ?, ?)",
        (parent, stamp, stamp),
    )
    if child:
        conn.execute(
            "INSERT OR IGNORE INTO categories (name, parent_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (f"{parent} / {child}", parent, stamp, stamp),
        )

    if owns_conn:
        conn.close()


def build_description(row: dict[str, str], description_col: str | None, type_col: str | None, detail_cols: list[str]) -> str:
    fields: list[str] = []

    if description_col:
        desc = (row.get(description_col) or "").strip()
        if desc:
            fields.append(desc)

    for col in detail_cols:
        value = (row.get(col) or "").strip()
        if value:
            fields.append(value)

    if type_col:
        op_type = (row.get(type_col) or "").strip()
        if op_type:
            fields.append(op_type)

    if not fields:
        for col in row:
            value = (row.get(col) or "").strip()
            if value:
                fields.append(value)

    unique: list[str] = []
    seen = set()
    for value in fields:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return " | ".join(unique)


def list_categories() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT name FROM categories ORDER BY name COLLATE NOCASE ASC").fetchall()
    existing = [r["name"] for r in rows]

    ordered: list[str] = []
    seen = set()
    for category in [*CATEGORIES, *existing]:
        if category and category not in seen:
            ordered.append(category)
            seen.add(category)
    return ordered


def list_category_tree() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT name, parent_name FROM categories ORDER BY name COLLATE NOCASE ASC").fetchall()

    tree_map: dict[str, list[str]] = {}
    for row in rows:
        parent = row["parent_name"]
        name = row["name"]
        if parent is None:
            tree_map.setdefault(name, [])
        else:
            tree_map.setdefault(parent, []).append(name)

    return [{"name": parent, "subcategories": sorted(children)} for parent, children in sorted(tree_map.items())]


def add_category(name: str, parent_name: str | None = None) -> dict[str, Any]:
    name = normalize_category(name)
    if not name:
        raise ValueError("Nom de catégorie vide")

    stamp = now_str()
    with get_conn() as conn:
        if parent_name:
            parent_name = normalize_category(parent_name)
            conn.execute(
                "INSERT OR IGNORE INTO categories (name, parent_name, created_at, updated_at) VALUES (?, NULL, ?, ?)",
                (parent_name, stamp, stamp),
            )
            full_name = f"{parent_name} / {name}"
            conn.execute(
                "INSERT OR IGNORE INTO categories (name, parent_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (full_name, parent_name, stamp, stamp),
            )
            return {"name": full_name, "parent_name": parent_name}

        conn.execute(
            "INSERT OR IGNORE INTO categories (name, parent_name, created_at, updated_at) VALUES (?, NULL, ?, ?)",
            (name, stamp, stamp),
        )
        return {"name": name, "parent_name": None}


def delete_category(name: str) -> dict[str, int]:
    target = normalize_category(name)
    if target == DEFAULT_CATEGORY:
        raise ValueError("Impossible de supprimer la catégorie par défaut")

    with get_conn() as conn:
        # Detect if it's a primary category
        is_primary = conn.execute("SELECT 1 FROM categories WHERE name = ? AND parent_name IS NULL", (target,)).fetchone() is not None

        if is_primary:
            pattern = f"{target} / %"
            tx = conn.execute(
                "UPDATE transactions SET category = ?, updated_at = ? WHERE category = ? OR category LIKE ?",
                (DEFAULT_CATEGORY, now_str(), target, pattern),
            ).rowcount
            conn.execute("DELETE FROM categories WHERE name = ? OR parent_name = ?", (target, target))
            return {"updated_transactions": tx}

        tx = conn.execute(
            "UPDATE transactions SET category = ?, updated_at = ? WHERE category = ?",
            (DEFAULT_CATEGORY, now_str(), target),
        ).rowcount
        conn.execute("DELETE FROM categories WHERE name = ?", (target,))
        return {"updated_transactions": tx}


def import_csv(content: bytes) -> dict[str, Any]:
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = content.decode("cp1252")

    delimiter = detect_delimiter(decoded)
    reader = csv.DictReader(io.StringIO(decoded), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return {"imported": 0}

    headers = reader.fieldnames or []
    date_col = detect_column(headers, ["date", "operation date", "transaction date", "date de l'opération"])
    amount_col = detect_column(headers, ["amount", "montant", "value"])
    category_col = detect_column(headers, ["category", "catégorie", "categorie"])
    sub_category_col = detect_column(headers, ["sous catégorie", "sous categorie", "sub category", "subcategory"])
    description_col = detect_column(headers, ["description", "label", "libellé", "libelle", "commentaire"])
    type_col = detect_column(headers, ["type de l'opération", "type de l'operation", "type"])

    detail_cols = [
        col
        for col in headers
        if col.lower().strip().startswith("détail") or col.lower().strip().startswith("detail")
    ]

    if not date_col or not amount_col:
        raise ValueError("Colonnes requises non détectées automatiquement (date, montant).")

    imported = 0
    stamp = now_str()
    with get_conn() as conn:
        for row in rows:
            if not any((row.get(h) or "").strip() for h in headers):
                continue

            description = build_description(row, description_col, type_col, detail_cols)
            if not description:
                continue

            date_val = parse_date(row[date_col])
            amount = parse_amount(row[amount_col])

            category_original = normalize_category(row.get(category_col) or DEFAULT_CATEGORY)
            sub_category = normalize_category(row.get(sub_category_col) or "") if sub_category_col else ""

            category = category_original
            if category == DEFAULT_CATEGORY:
                category = infer_category(description)

            if sub_category and sub_category != DEFAULT_CATEGORY and category != DEFAULT_CATEGORY:
                category = f"{category} / {sub_category}"

            ensure_category_exists(category, conn=conn)

            conn.execute(
                """
                INSERT INTO transactions (
                    date, description, amount_original, amount_effective, category,
                    category_original, is_excluded, split_ratio, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 1.0, ?, ?)
                """,
                (date_val, description, amount, amount, category, category_original, stamp, stamp),
            )
            imported += 1

    return {"imported": imported}


def build_filters(args: dict[str, str], include_excluded_default: bool = False) -> tuple[str, list[Any]]:
    where = []
    params: list[Any] = []

    if args.get("month"):
        where.append("strftime('%m', date) = ?")
        params.append(f"{int(args['month']):02d}")
    if args.get("year"):
        where.append("strftime('%Y', date) = ?")
        params.append(str(int(args["year"])))
    if args.get("start_date"):
        where.append("date >= ?")
        params.append(args["start_date"])
    if args.get("end_date"):
        where.append("date <= ?")
        params.append(args["end_date"])
    if args.get("category"):
        where.append("category = ?")
        params.append(args["category"])
    if args.get("parent_category"):
        where.append("(category = ? OR category LIKE ?)")
        params.append(args["parent_category"])
        params.append(f"{args['parent_category']} / %")
    if args.get("search"):
        where.append("lower(description) LIKE ?")
        params.append(f"%{args['search'].lower()}%")
    if args.get("uncategorized") == "1":
        where.append("category = ?")
        params.append(DEFAULT_CATEGORY)

    include_excluded = args.get("include_excluded", "1" if include_excluded_default else "0") == "1"
    excluded_only = args.get("excluded_only", "0") == "1"
    if excluded_only:
        where.append("is_excluded = 1")
    elif not include_excluded:
        where.append("is_excluded = 0")

    where_clause = " WHERE " + " AND ".join(where) if where else ""
    return where_clause, params


def summary(args: dict[str, str]) -> dict[str, float]:
    where_clause, params = build_filters(args)
    q = f"""
        SELECT
            COALESCE(SUM(CASE WHEN amount_original < 0 THEN ABS(amount_effective) ELSE 0 END), 0) AS expenses,
            COALESCE(SUM(CASE WHEN amount_original >= 0 THEN amount_effective ELSE 0 END), 0) AS income
        FROM transactions
        {where_clause}
    """
    with get_conn() as conn:
        row = conn.execute(q, params).fetchone()
    expenses = float(row["expenses"])
    income = float(row["income"])
    return {"expenses": expenses, "income": income, "balance": income - expenses}


def category_breakdown(args: dict[str, str]) -> list[dict[str, Any]]:
    where_clause, params = build_filters(args)
    level = args.get("level", "primary")

    if level == "secondary":
        q = f"""
            SELECT category,
                   COALESCE(SUM(CASE WHEN amount_original < 0 THEN ABS(amount_effective) ELSE 0 END), 0) AS amount
            FROM transactions
            {where_clause}
            GROUP BY category
            HAVING amount > 0
            ORDER BY amount DESC
        """
    else:
        q = f"""
            SELECT primary_category AS category,
                   SUM(amount_part) AS amount
            FROM (
                SELECT
                    CASE
                        WHEN instr(category, ' / ') > 0 THEN substr(category, 1, instr(category, ' / ') - 1)
                        ELSE category
                    END AS primary_category,
                    CASE WHEN amount_original < 0 THEN ABS(amount_effective) ELSE 0 END AS amount_part
                FROM transactions
                {where_clause}
            ) grouped
            GROUP BY primary_category
            HAVING amount > 0
            ORDER BY amount DESC
        """

    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()

    total = sum(float(r["amount"]) for r in rows) or 1.0
    return [
        {"category": r["category"], "amount": float(r["amount"]), "percentage": round(float(r["amount"]) * 100 / total, 2)}
        for r in rows
    ]


def monthly_stats(args: dict[str, str]) -> list[dict[str, Any]]:
    where_clause, params = build_filters(args)
    q = f"""
        SELECT substr(date, 1, 7) AS month,
               COALESCE(SUM(CASE WHEN amount_original < 0 THEN ABS(amount_effective) ELSE 0 END), 0) AS expenses,
               COALESCE(SUM(CASE WHEN amount_original >= 0 THEN amount_effective ELSE 0 END), 0) AS income
        FROM transactions
        {where_clause}
        GROUP BY month
        ORDER BY month ASC
    """
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [{"month": r["month"], "expenses": float(r["expenses"]), "income": float(r["income"])} for r in rows]


def get_transactions(args: dict[str, str]) -> list[dict[str, Any]]:
    where_clause, params = build_filters(args, include_excluded_default=True)
    q = f"""
        SELECT id, date, description, amount_original, amount_effective,
               category, category_original, is_excluded, split_ratio
        FROM transactions
        {where_clause}
        ORDER BY date DESC, id DESC
        LIMIT 1000
    """
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def update_transaction(transaction_id: int, payload: dict[str, Any]) -> None:
    fields = []
    params: list[Any] = []

    if "category" in payload:
        category = normalize_category(payload["category"])
        ensure_category_exists(category)
        fields.append("category = ?")
        params.append(category)
    if "is_excluded" in payload:
        fields.append("is_excluded = ?")
        params.append(1 if payload["is_excluded"] else 0)
    if "split_ratio" in payload:
        split_ratio = min(max(float(payload["split_ratio"]), 0.0), 1.0)
        fields.append("split_ratio = ?")
        params.append(split_ratio)
        fields.append("amount_effective = amount_original * ?")
        params.append(split_ratio)

    fields.append("updated_at = ?")
    params.append(now_str())
    params.append(transaction_id)

    with get_conn() as conn:
        conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?", params)


def bulk_update(ids: list[int], category: str) -> int:
    if not ids:
        return 0
    category = normalize_category(category)
    ensure_category_exists(category)
    placeholders = ",".join("?" for _ in ids)
    with get_conn() as conn:
        result = conn.execute(
            f"UPDATE transactions SET category = ?, updated_at = ? WHERE id IN ({placeholders})",
            [category, now_str(), *ids],
        )
    return result.rowcount


def reset_db() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM transactions")


def export_filtered_transactions(args: dict[str, str]) -> list[dict[str, Any]]:
    return get_transactions(args)
