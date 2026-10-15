# csv2ddl

Infer column types from a CSV and print a `CREATE TABLE` statement for ANSI SQL, Postgres, T-SQL (SQL Server or Azure SQL) or Spark. It uses only the Python standard library.

```bash
python3 csv2ddl.py samples/trades.csv
python3 csv2ddl.py samples/trades.csv --dialect tsql --table stg_trades
python3 csv2ddl.py big.csv --sample 10000   # scan only the first 10k rows
```

```sql
CREATE TABLE "trades" (
  "trade_id" BIGINT NOT NULL,
  "account" VARCHAR(16) NOT NULL,
  "amount" DECIMAL(8,3) NOT NULL,
  "is_reversal" BOOLEAN NOT NULL,
  "trade_date" DATE NOT NULL,
  "booked_at" TIMESTAMP NOT NULL,
  "note" VARCHAR(32)
);
```

## Rules

- Each column gets the narrowest type that fits every non-empty value: BOOLEAN, BIGINT, DECIMAL(p,s), DATE, TIMESTAMP, or VARCHAR as the fallback.
- DECIMAL precision and scale come from the widest whole part and the longest fraction that were seen.
- VARCHAR widths are rounded up to a power of two, with at least 25% headroom.
- A column with any empty value is nullable. Otherwise it's `NOT NULL`.
- Integers outside the 64-bit range fall back to DECIMAL.

Treat the output as a starting draft and review it before running it in production. A sample can miss rare values.

## Tests

```bash
python3 -m unittest
```
