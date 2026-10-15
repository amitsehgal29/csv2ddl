import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import csv2ddl as c


def col(values):
    x = c.Col("x")
    for v in values:
        x.add(v)
    return x


A = c.DIALECT["ansi"]


class TypeTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(col(["1", "-2"]).sql_type(A), "BIGINT")
        self.assertEqual(col(["true", "N"]).sql_type(A), "BOOLEAN")
        self.assertEqual(col(["2026-10-14"]).sql_type(A), "DATE")
        self.assertEqual(col(["2026-10-14", "2026-10-14T09:00:00Z"]).sql_type(A), "TIMESTAMP")

    def test_decimal_precision_and_scale(self):
        self.assertEqual(col(["1500.25", "-320.5", "99999.125", "7"]).sql_type(A), "DECIMAL(8,3)")

    def test_mixed_falls_back_to_varchar(self):
        self.assertEqual(col(["1", "abc"]).sql_type(A), "VARCHAR(16)")
        self.assertEqual(col(["x" * 30]).sql_type(A), "VARCHAR(64)")

    def test_huge_int_is_not_bigint(self):
        self.assertNotEqual(col([str(2**70)]).sql_type(A), "BIGINT")

    def test_nullability(self):
        self.assertTrue(col(["1", ""]).nullable)
        self.assertFalse(col(["1"]).nullable)


class CliTests(unittest.TestCase):
    def run_cli(self, *a):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(c.main([str(Path(__file__).parent / "samples" / "trades.csv"), *a]), 0)
        return out.getvalue()

    def test_ansi(self):
        s = self.run_cli()
        self.assertIn('CREATE TABLE "trades"', s)
        self.assertIn('"trade_id" BIGINT NOT NULL', s)
        self.assertIn('"is_reversal" BOOLEAN NOT NULL', s)
        self.assertIn('"note" VARCHAR(32)', s)
        self.assertNotIn('"note" VARCHAR(32) NOT NULL', s)

    def test_tsql(self):
        s = self.run_cli("--dialect", "tsql", "--table", "stg_trades")
        self.assertIn("[is_reversal] BIT", s)
        self.assertIn("[booked_at] DATETIME2", s)


if __name__ == "__main__":
    unittest.main()
