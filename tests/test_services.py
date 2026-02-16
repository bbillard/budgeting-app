import os
import tempfile
import unittest

from db import get_conn, init_db
from services import import_csv, parse_amount


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
        self.assertIn("PASCALE BILLARD", rows[1]["description"])

        self.assertEqual(rows[2]["category"], "Revenus / Autres revenus")
        self.assertAlmostEqual(rows[2]["amount_original"], 3552.75)


if __name__ == "__main__":
    unittest.main()
