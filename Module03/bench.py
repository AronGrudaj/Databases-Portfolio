"""Module 3 / Task 2 - index benchmark. Run from the repo root:  python Module03/bench.py
For every step (baseline, then one index added at a time) it prints the
EXPLAIN QUERY PLAN and the MEDIAN wall-clock time of each query (REPEATS runs)."""
import sqlite3, statistics, time
from pathlib import Path

DB = Path(__file__).with_name("warehouse.db")
REPEATS = 5          # >= 3 required; the first run pays for the file cache, the median hides it
BATCH = 200          # for sub-millisecond queries: time BATCH executions, divide

QUERIES = {
    "dashboard (aggregate, 2025)": ("""
        SELECT c.city, COUNT(DISTINCT c.customer_id) AS customers, SUM(ol.qty * p.price) AS revenue
        FROM customer c
        JOIN orders o      ON o.customer_id = c.customer_id
        JOIN order_line ol ON ol.order_id   = o.order_id
        JOIN product p     ON p.product_id  = ol.product_id
        WHERE o.ordered_on >= '2025-01-01' AND o.ordered_on < '2026-01-01'
        GROUP BY c.city ORDER BY revenue DESC""", 1),
    "single-day lookup": ("""
        SELECT o.order_id, o.ordered_on, c.name
        FROM orders o JOIN customer c ON c.customer_id = o.customer_id
        WHERE o.ordered_on = '2026-02-14'""", BATCH),
    "filter on ol.product_id": ("""
        SELECT ol.order_id, ol.qty FROM order_line ol WHERE ol.product_id = 42""", 20),
    "NEGATIVE: date(ordered_on)=": ("""
        SELECT order_id FROM orders WHERE date(ordered_on) = '2026-02-14'""", 20),
}

STEPS = [
    ("baseline (no extra index)", None),
    ("+ ix_orders_ordered_on",  "CREATE INDEX ix_orders_ordered_on ON orders(ordered_on)"),
    ("+ ix_orderline_order",    "CREATE INDEX ix_orderline_order ON order_line(order_id)"),
    ("+ ix_orderline_product",  "CREATE INDEX ix_orderline_product ON order_line(product_id)"),
]

def plan(conn, sql):
    return [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql)]

def median_ms(conn, sql, batch):
    runs = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        for _ in range(batch):
            conn.execute(sql).fetchall()
        runs.append((time.perf_counter() - t0) / batch * 1000)
    return statistics.median(runs)

conn = sqlite3.connect(DB)
for ix in ("ix_orders_ordered_on", "ix_orderline_order", "ix_orderline_product"):
    conn.execute(f"DROP INDEX IF EXISTS {ix}")           # reset benchmark state

print(f"SQLite {sqlite3.sqlite_version}, {REPEATS} runs per cell, median reported\n")
table = {}
for label, ddl in STEPS:
    if ddl: conn.execute(ddl)
    print(f"=== {label} ===")
    for name, (sql, batch) in QUERIES.items():
        ms = median_ms(conn, sql, batch)
        table.setdefault(name, []).append(ms)
        print(f"  [{ms:9.3f} ms] {name}")
        for line in plan(conn, sql): print(f"        {line}")
    print()

print("SUMMARY (median ms)")
print(f"{'query':32}" + "".join(f"{s[0][:22]:>24}" for s in STEPS))
for name, vals in table.items():
    print(f"{name:32}" + "".join(f"{v:24.3f}" for v in vals))
