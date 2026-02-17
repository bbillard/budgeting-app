import os
import tempfile
import unittest

from db import get_conn, init_db
from services import (
    add_category,
    category_breakdown,
    delete_category,
    import_csv,
    list_categories,
    monthly_breakdown,
    parse_amount,
    build_filters,
)


SAMPLE_BANK_CSV = """Date de l'opération;Référence de l'opération;Type de l'opération;Catégorie;Sous catégorie;Montant;Commentaire;Détail 1;Détail 2;Détail 3;Détail 4;Détail 5;Détail 6
30/01/2026;3029544;CARTE               ;Alimentation;Supermarché;-2,75;;CARREFOUR CITY            LE 29/01/26                                         ;REF  CB.XXXXX8067                                                            ;
30/01/2026;0f11026;VIREMENT INSTANTANE EMIS;A catégoriser;A catégoriser;-14,30;;PASCALE BILLARD                                                               ;FLEURS MICHEL                                                                ;WERO                                                                         ;
28/01/2026;2854888;VIREMENT SEPA RECU  ;Revenus;Autres revenus;3552,75;;NIJI                                                                          ;VIREMENT MOIS DE JANVIER 2026-954                                            ;CCBPFRPPNAN                                                                  ;
"""


class TestServices(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BUDGET_DB_PATH"] = os.path.join(self.tmp.name, "test_budget.db")
        init_db()

    def tearDown(self):
        os.environ.pop("BUDGET_DB_PATH", None)
        self.tmp.cleanup()

    def test_parse_amount_euro_format(self):
        self.assertEqual(parse_amount("1 234,56 €"), 1234.56)

    def test_import_csv_semicolon_french_bank_format(self):
        result = import_csv(SAMPLE_BANK_CSV.encode("utf-8"))
        self.assertEqual(result["imported"], 3)

        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, description, amount_original, category, category_original FROM transactions ORDER BY id"
            ).fetchall()

        self.assertEqual(rows[0]["date"], "2026-01-30")
        self.assertAlmostEqual(rows[0]["amount_original"], -2.75)
        self.assertEqual(rows[0]["category_original"], "Alimentation")
        self.assertEqual(rows[0]["category"], "Alimentation / Supermarché")
        self.assertIn("CARREFOUR CITY", rows[0]["description"])

        self.assertEqual(rows[1]["category_original"], "À catégoriser")
        self.assertEqual(rows[1]["category"], "À catégoriser")

        self.assertEqual(rows[2]["category"], "Revenus / Autres revenus")
        self.assertAlmostEqual(rows[2]["amount_original"], 3552.75)

    def test_list_categories_includes_imported_compound_categories(self):
        import_csv(SAMPLE_BANK_CSV.encode("utf-8"))
        categories = list_categories()

        self.assertIn("Alimentation / Supermarché", categories)
        self.assertIn("Revenus / Autres revenus", categories)
        self.assertIn("Logement", categories)

    def test_delete_category_moves_transactions_to_uncategorized(self):
        import_csv(SAMPLE_BANK_CSV.encode("utf-8"))
        result = delete_category("Alimentation")
        self.assertGreaterEqual(result["updated_transactions"], 1)

        with get_conn() as conn:
            row = conn.execute(
                "SELECT category FROM transactions WHERE description LIKE '%CARREFOUR CITY%'"
            ).fetchone()
        self.assertEqual(row["category"], "À catégoriser")

    def test_breakdown_primary_level_groups_subcategories(self):
        import_csv(SAMPLE_BANK_CSV.encode("utf-8"))

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO transactions (
                    date, description, amount_original, amount_effective, category,
                    category_original, is_excluded, split_ratio, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 1.0, ?, ?)
                """,
                (
                    "2026-01-27",
                    "Test restaurant",
                    -10.0,
                    -10.0,
                    "Alimentation / Restaurant",
                    "Alimentation",
                    "2026-01-27 00:00:00",
                    "2026-01-27 00:00:00",
                ),
            )

        result = category_breakdown({"level": "primary"})
        by_name = {r["category"]: r["amount"] for r in result}

        self.assertIn("Alimentation", by_name)
        self.assertEqual(sum(1 for r in result if r["category"] == "Alimentation"), 1)
        self.assertAlmostEqual(by_name["Alimentation"], 12.75)
        self.assertIn("À catégoriser", by_name)

    def test_add_subcategory(self):
        created = add_category("Boulangerie", "Alimentation")
        self.assertEqual(created["name"], "Alimentation / Boulangerie")
        self.assertIn("Alimentation / Boulangerie", list_categories())


    def test_build_filters_supports_multiple_months_years_and_categories(self):
        where, params = build_filters({
            "months": "1||2",
            "years": "2025||2026",
            "categories": "Alimentation / Supermarché||Vie quotidienne / Beauté",
        })

        self.assertIn("strftime('%m', date) IN (?,?)", where)
        self.assertIn("strftime('%Y', date) IN (?,?)", where)
        self.assertIn("(category = ? OR category = ?)", where)
        self.assertEqual(params[:2], ["01", "02"])
        self.assertEqual(params[2:4], ["2025", "2026"])
        self.assertEqual(params[4:6], ["Alimentation / Supermarché", "Vie quotidienne / Beauté"])

    def test_build_filters_primary_category_matches_subcategories(self):
        where, params = build_filters({"categories": "Alimentation"})

        self.assertIn("(category = ? OR category LIKE ?)", where)
        self.assertEqual(params, ["Alimentation", "Alimentation / %"])

    def test_monthly_breakdown_supports_primary_and_filtered_secondary(self):
        import_csv(SAMPLE_BANK_CSV.encode("utf-8"))

        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO transactions (
                    date, description, amount_original, amount_effective, category,
                    category_original, is_excluded, split_ratio, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 1.0, ?, ?)
                """,
                (
                    "2026-02-03",
                    "Test telecommunication",
                    -20.0,
                    -20.0,
                    "Vie quotidienne / Télécommunication",
                    "Vie quotidienne",
                    "2026-02-03 00:00:00",
                    "2026-02-03 00:00:00",
                ),
            )
            conn.execute(
                """
                INSERT INTO transactions (
                    date, description, amount_original, amount_effective, category,
                    category_original, is_excluded, split_ratio, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 1.0, ?, ?)
                """,
                (
                    "2026-02-04",
                    "Test beauté",
                    -30.0,
                    -30.0,
                    "Vie quotidienne / Beauté",
                    "Vie quotidienne",
                    "2026-02-04 00:00:00",
                    "2026-02-04 00:00:00",
                ),
            )

        primary = monthly_breakdown({"level": "primary"})
        feb = next(item for item in primary if item["month"] == "2026-02")
        self.assertEqual(feb["categories"][0]["category"], "Vie quotidienne")
        self.assertAlmostEqual(feb["total"], 50.0)
        self.assertEqual(sum(1 for c in feb["categories"] if c["category"] == "Vie quotidienne"), 1)

        secondary = monthly_breakdown({"level": "secondary", "parent_category": "Vie quotidienne"})
        feb_sec = next(item for item in secondary if item["month"] == "2026-02")
        labels = [c["category"] for c in feb_sec["categories"]]
        self.assertIn("Vie quotidienne / Télécommunication", labels)
        self.assertIn("Vie quotidienne / Beauté", labels)


if __name__ == "__main__":
    unittest.main()
