from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from categorization import DEFAULT_CATEGORY, infer_category
from db import get_conn


DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


CATEGORIES = [
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


def parse_amount(raw: str) -> float:
    cleaned = raw.replace("€", "").replace(" ", "").replace(",", ".")
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
    lowered = {h.lower(): h for h in headers}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def import_csv(content: bytes) -> dict[str, Any]:
    decoded = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    rows = list(reader)
    if not rows:
        return {"imported": 0}

    headers = reader.fieldnames or []
    date_col = detect_column(headers, ["date", "operation date", "transaction date"])
    desc_col = detect_column(headers, ["description", "label", "libellé", "libelle"])
    amount_col = detect_column(headers, ["amount", "montant", "value"])
    category_col = detect_column(headers, ["category", "catégorie", "categorie"])

    if not date_col or not desc_col or not amount_col:
        raise ValueError("Colonnes requises non détectées automatiquement (date, description, montant).")

    now = datetime.now().strftime(DATETIME_FMT)
    imported = 0
    with get_conn() as conn:
        for row in rows:
            description = (row.get(desc_col) or "").strip()
            if not description:
                continue
            date_val = parse_date(row[date_col])
            amount = parse_amount(row[amount_col])
            category_original = (row.get(category_col) or DEFAULT_CATEGORY).strip() if category_col else DEFAULT_CATEGORY
            category = category_original
            if not category or category.lower() == "à catégoriser":
                category = infer_category(description)

            conn.execute(
                """
                INSERT INTO transactions (
                    date, description, amount_original, amount_effective, category,
                    category_original, is_excluded, split_ratio, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 1.0, ?, ?)
                """,
                (date_val, description, amount, amount, category, category_original or DEFAULT_CATEGORY, now, now),
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
    q = f"""
        SELECT category,
               COALESCE(SUM(CASE WHEN amount_original < 0 THEN ABS(amount_effective) ELSE 0 END), 0) AS amount
        FROM transactions
        {where_clause}
        GROUP BY category
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
        fields.append("category = ?")
        params.append(payload["category"])
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
    params.append(datetime.now().strftime(DATETIME_FMT))
    params.append(transaction_id)

    with get_conn() as conn:
        conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?", params)


def bulk_update(ids: list[int], category: str) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    with get_conn() as conn:
        result = conn.execute(
            f"UPDATE transactions SET category = ?, updated_at = ? WHERE id IN ({placeholders})",
            [category, datetime.now().strftime(DATETIME_FMT), *ids],
        )
    return result.rowcount


def reset_db() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM transactions")


def export_filtered_transactions(args: dict[str, str]) -> list[dict[str, Any]]:
    return get_transactions(args)
