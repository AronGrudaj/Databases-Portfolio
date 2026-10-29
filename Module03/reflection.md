# Module 3 Reflection: LLM-Assisted SQL and Query Profiling

**Environment:** sqlite3 CLI 3.53.4, Python's SQLite 3.37.2, Windows.
**Evidence in my repo:** `Module03/` (`setup.sql`, `legacy_standin.sql`, `bench.py`, `bench_output.txt`, `injection_demo.py`, `injection_output.txt`, `task1_plan.txt`, `demo.py`, `sql-notes.md`).

## 1. What I did

I built a warehouse database with 2,000 customers, 500 products, 60,000 orders and 240,000 order lines. I asked an LLM to write a reporting query, then checked it three ways: does it run, is it correct, and is it fast and safe. I read query plans with `EXPLAIN QUERY PLAN`, tested three indexes one at a time, wrote relational algebra for a query, and broke and fixed a SQL injection.

I did not have my Module 2 database, so an LLM generated a stand-in (`legacy_standin.sql`) with the same table and column names. I labelled it as a stand-in in my notes.

## 2. My guesses and what actually happened

Before running each query I wrote down whether I expected `SCAN` or `SEARCH`. Here is what the plans really showed and why.

| Query | My guess (written before running) | What happened | Why |
|---|---|---|---|
| `technician = 'Beier'`, no index | ___ | `SCAN` | no index existed, so SQLite read every row |
| same query after `ix_job_tech` | ___ | `SEARCH ... USING INDEX` | the index matches the filter column |
| `machine_name = 'cnc-02'` | ___ | `SCAN` | nothing is indexed on that column |
| `technician LIKE '%ei%'` after the index | ___ | `SCAN` | a leading `%` gives a sorted index nowhere to start |
| `lower(technician) = 'beier'` after the index | ___ | `SCAN` | the function hides the column from the index |
| Task 1 dashboard query | ___ | `SCAN ol`, then `SEARCH` on `o`, `c` and `p` by primary key | SQLite starts from the biggest table and reaches the others through their primary keys |

Every wrong guess in this table taught me something about how the engine thinks, and I kept them in my notes on purpose.

## 3. What I learned

### The plan tells me what happened, the timer only tells me how long
`SCAN` means SQLite reads every row. `SEARCH` means it jumps through an index. A covering index means the index holds every column the query needs, so the table is never opened. Two identical runs gave different times, but the plan stayed the same, so I trust the plan more and use the timer to confirm.

### An index can make a query slower
This was my biggest surprise. These are my own benchmark results (median of 5 runs):

| Query | Baseline | + `ix_orders_ordered_on` | + `ix_orderline_order` | + `ix_orderline_product` |
|---|---:|---:|---:|---:|
| Dashboard (2025 revenue per city) | 124 ms | 127 ms | **1075 ms** | 1047 ms |
| Single-day lookup | 2.9 ms | 0.22 ms | 0.21 ms | 0.21 ms |
| Filter on `product_id` | 11.4 ms | 11.6 ms | 10.3 ms | **1.9 ms** |
| `date(ordered_on) = ...` (negative test) | 14.8 ms | 13.0 ms | 12.9 ms | 12.9 ms |

- `ix_orderline_order` changed the dashboard plan, but the query became about **8 times slower**. The 2025 filter keeps about two thirds of all orders, so tens of thousands of index lookups cost more than one straight scan.
- `ix_orders_ordered_on` made the single-day lookup about **13 times faster** (`SCAN` became `SEARCH`).
- `ix_orderline_product` did nothing for the dashboard, because SQLite reaches `product` by primary key. It made a `product_id` filter about **6 times faster**. So an index is useful for specific queries, not good or bad in general.
- A negative result: `date(ordered_on) = ...` stays a scan. With the index it scans the smaller index instead of the table, but it never becomes a `SEARCH`, because the function wraps the column.

### Checking the LLM's SQL
The LLM's query ran and matched an independent Python recomputation. I also learned the traps that LLM-written reports fall into:
- `COUNT(DISTINCT customer_id)` is needed, because joins repeat each customer once per order line.
- `BETWEEN '2025-01-01' AND '2026-01-01'` wrongly includes 2026-01-01 and counts 40,686 orders instead of 40,575. A half-open range (`>= ... AND < ...`) is correct.
- `strftime('%Y', ordered_on) = '2025'` wraps the column in a function, so the index cannot be used for a range search.
- An inner join drops cities with no orders, so I have to decide whether that matches the question.

### SQL clauses and relational algebra
SQL is evaluated as FROM, WHERE, GROUP BY, HAVING, SELECT, then ORDER BY, which is not the order it is written in. That is why an aggregate in `WHERE` fails and needs `HAVING`. In algebra, σ is WHERE, π is the SELECT list, ⋈ is JOIN and γ is GROUP BY. I wrote the algebra for a single-day lookup, compared it with an LLM's version, and found it was equivalent. The LLM only added renames (ρ) for the aliases. I also learned that SQLite accepts a `SELECT` alias in `WHERE` even though the standard does not, so I should test claims on the engine I use.

### SQL injection
My demo showed it directly:
- `O'Brien` crashed the unsafe query with `syntax error near "Brien"`.
- The payload `' OR '1'='1` made the unsafe query return all 2,000 customers.
- The same inputs against the safe query returned 0 rows.

The fix is a bound parameter: write `WHERE name = ?` and pass the value separately as `(name,)`. The database then receives the query and the value apart, so the value is only data. Escaping quotes by hand is not enough, because it does not cover numbers, table names, or different encodings, and the developer must get it right every time. A driver that refuses two statements at once only blocks one attack style, so "my table wasn't dropped" does not prove the code is safe.

### The stretcher: three ways to count late orders
`GROUP BY` was fastest and simplest (about 6 ms, 400 rows). The correlated subquery took about 3.9 seconds without an index and returned 2,000 rows, because it includes customers with zero late orders, so it was not equivalent. With an index on `orders(customer_id, status)` it dropped to about 3 ms. The window function needed `DISTINCT` and was a bit slower. The result depends on what I need, not on one style being best.

## 4. How I verified AI output

- I ran the query and compared the result with a separate calculation instead of trusting how plausible it looked.
- I checked the specific traps: duplicates after joins, the date boundary, and functions around indexed columns.
- I wrote my guesses before running anything and recorded where I was wrong.
- I tested the LLM's index suggestions one at a time. Testing them separately is what showed me that one of them made the query slower.
- I tested claims on my own engine, which exposed a SQLite-specific behaviour.

## 5. What was hard

Reading plans was the hardest part: telling `SCAN` from `SEARCH`, and understanding that a plan can change without the query getting faster. Setting up the project on a second laptop also showed me that an empty `warehouse.db` gives confusing `no such table` errors, so I now check the file size and row counts first.

## 6. Open questions

- Why does a function-wrapped column still use the index for a full scan but not for a search?
- Does the alias-in-`WHERE` behaviour exist outside SQLite?
- How much does the planner's choice change when table statistics are updated with `ANALYZE`?

## 7. What I will do differently

I will predict the plan before I run a query, check the result with a second method, test one index at a time, and use bound parameters for every query that takes user input.
