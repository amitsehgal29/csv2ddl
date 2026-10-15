#!/usr/bin/env python3
"""csv2ddl: infer column types from a CSV and print a CREATE TABLE statement.

Standard library only. Each column is scanned (all rows, or --sample N) and
gets the narrowest type that fits every non-empty value:
  BOOLEAN < BIGINT < DECIMAL(p,s) < TIMESTAMP / DATE < VARCHAR(n)
A column with any empty value is NULLable; otherwise NOT NULL.
Dialects: ansi (default), postgres, tsql (SQL Server / Azure SQL), spark.
"""
import argparse
import csv
import re
import sys
from datetime import date, datetime

BOOL = {"true", "false", "t", "f", "yes", "no", "y", "n"}
INT_RE = re.compile(r"^[+-]?\d+$")
DEC_RE = re.compile(r"^[+-]?(\d*)\.(\d+)$")
INT64 = 2**63

DIALECT = {
    "ansi": {"BOOLEAN": "BOOLEAN", "BIGINT": "BIGINT", "TIMESTAMP": "TIMESTAMP", "DATE": "DATE", "VARCHAR": "VARCHAR({n})", "q": '"{}"'},
    "postgres": {"BOOLEAN": "BOOLEAN", "BIGINT": "BIGINT", "TIMESTAMP": "TIMESTAMPTZ", "DATE": "DATE", "VARCHAR": "VARCHAR({n})", "q": '"{}"'},
    "tsql": {"BOOLEAN": "BIT", "BIGINT": "BIGINT", "TIMESTAMP": "DATETIME2", "DATE": "DATE", "VARCHAR": "NVARCHAR({n})", "q": "[{}]"},
    "spark": {"BOOLEAN": "BOOLEAN", "BIGINT": "BIGINT", "TIMESTAMP": "TIMESTAMP", "DATE": "DATE", "VARCHAR": "STRING", "q": "`{}`"},
}


def kind(v):
    """Return the narrowest kind for one non-empty value."""
    if v.lower() in BOOL:
        return "BOOLEAN"
    if INT_RE.match(v) and -INT64 <= int(v) < INT64:
        return "BIGINT"
    if DEC_RE.match(v):
        return "DECIMAL"
    try:
        date.fromisoformat(v)
        if len(v) == 10:
            return "DATE"
    except ValueError:
        pass
    t = v[:-1] + "+00:00" if v[-1:] in "Zz" else v
    try:
        datetime.fromisoformat(t)
        return "TIMESTAMP"
    except ValueError:
        return "VARCHAR"


class Col:
    def __init__(self, name):
        self.name, self.kinds, self.nullable, self.maxlen = name, set(), False, 0
        self.int_digits, self.scale = 0, 0

    def add(self, v):
        v = v.strip()
        if v == "":
            self.nullable = True
            return
        self.maxlen = max(self.maxlen, len(v))
        k = kind(v)
        self.kinds.add(k)
        num = v.lstrip("+-")
        if k in ("BIGINT", "DECIMAL"):
            whole, _, frac = num.partition(".")
            self.int_digits = max(self.int_digits, len(whole.lstrip("0")) or 1)
            self.scale = max(self.scale, len(frac))

    def sql_type(self, d):
        ks = self.kinds
        if not ks:
            return d["VARCHAR"].format(n=1)
        if ks == {"BOOLEAN"}:
            return d["BOOLEAN"]
        if ks == {"BIGINT"}:
            return d["BIGINT"]
        if ks <= {"BIGINT", "DECIMAL"}:
            p = min(self.int_digits + self.scale, 38)
            return f"DECIMAL({p},{min(self.scale, p)})"
        if ks == {"DATE"}:
            return d["DATE"]
        if ks <= {"DATE", "TIMESTAMP"}:
            return d["TIMESTAMP"]
        # round VARCHAR width up to a friendly size with headroom
        n = 16
        while n < self.maxlen * 1.25:
            n *= 2
        return d["VARCHAR"].format(n=n)


def infer(rows, fields):
    cols = [Col(f) for f in fields]
    for row in rows:
        for c in cols:
            c.add(row.get(c.name) or "")
    return cols


def ddl(table, cols, dialect="ansi"):
    d = DIALECT[dialect]
    lines = []
    for c in cols:
        null = " NOT NULL" if not c.nullable and c.kinds else ""
        lines.append(f"  {d['q'].format(c.name)} {c.sql_type(d)}{null}")
    return f"CREATE TABLE {d['q'].format(table)} (\n" + ",\n".join(lines) + "\n);"


def main(argv=None):
    p = argparse.ArgumentParser(description="Infer a CREATE TABLE statement from a CSV.")
    p.add_argument("source")
    p.add_argument("--table", help="table name (default: file name without .csv)")
    p.add_argument("--dialect", choices=sorted(DIALECT), default="ansi")
    p.add_argument("--sample", type=int, default=0, help="scan only the first N rows (default: all)")
    args = p.parse_args(argv)
    table = args.table or re.sub(r"\.csv$", "", args.source.rsplit("/", 1)[-1], flags=re.I)
    with open(args.source, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if not fields:
            print("csv2ddl: no header row", file=sys.stderr)
            return 2
        rows = []
        for i, r in enumerate(reader):
            if args.sample and i >= args.sample:
                break
            rows.append(r)
    print(ddl(table, infer(rows, fields), args.dialect))
    return 0


if __name__ == "__main__":
    sys.exit(main())
