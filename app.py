from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from db import init_db
from services import (
    add_category,
    bulk_update,
    category_breakdown,
    delete_category,
    export_filtered_transactions,
    get_transactions,
    import_csv,
    list_categories,
    list_category_tree,
    monthly_breakdown,
    monthly_stats,
    reset_db,
    summary,
    update_transaction,
)

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/summary")
def api_summary():
    return jsonify(summary(request.args.to_dict()))


@app.get("/api/categories-breakdown")
def api_category_breakdown():
    return jsonify(category_breakdown(request.args.to_dict()))


@app.get("/api/monthly")
def api_monthly():
    return jsonify(monthly_stats(request.args.to_dict()))


@app.get("/api/monthly-breakdown")
def api_monthly_breakdown():
    return jsonify(monthly_breakdown(request.args.to_dict()))


@app.get("/api/categories")
def api_categories():
    return jsonify(list_categories())


@app.get("/api/categories/tree")
def api_categories_tree():
    return jsonify(list_category_tree())


@app.post("/api/categories")
def api_add_category():
    payload = request.get_json(force=True)
    created = add_category(payload.get("name", ""), payload.get("parent_name"))
    return jsonify(created)


@app.post("/api/categories/delete")
def api_delete_category():
    payload = request.get_json(force=True)
    result = delete_category(payload.get("name", ""))
    return jsonify(result)


@app.get("/api/transactions")
def api_transactions():
    return jsonify(get_transactions(request.args.to_dict()))


@app.post("/api/transactions/<int:transaction_id>")
def api_transaction_update(transaction_id: int):
    payload = request.get_json(force=True)
    update_transaction(transaction_id, payload)
    return jsonify({"status": "ok"})


@app.post("/api/transactions/bulk-update")
def api_bulk_update():
    payload = request.get_json(force=True)
    updated = bulk_update(payload.get("ids", []), payload.get("category", "Autres"))
    return jsonify({"updated": updated})


@app.post("/api/import-csv")
def api_import_csv():
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "Aucun fichier fourni"}), 400
    try:
        return jsonify(import_csv(file.read()))
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@app.post("/api/reset")
def api_reset():
    reset_db()
    return jsonify({"status": "ok"})


@app.get("/api/export.csv")
def api_export_csv():
    rows = export_filtered_transactions(request.args.to_dict())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=rows[0].keys() if rows else ["id"])
    writer.writeheader()
    writer.writerows(rows)
    byte_file = io.BytesIO(buffer.getvalue().encode("utf-8"))
    byte_file.seek(0)
    return send_file(byte_file, mimetype="text/csv", as_attachment=True, download_name="transactions_export.csv")


@app.get("/api/backup.json")
def api_backup_json():
    rows = export_filtered_transactions(request.args.to_dict())
    out = Path("data") / "backup.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"path": str(out), "rows": len(rows)})


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
