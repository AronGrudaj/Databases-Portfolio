# Module 3 — sql-notes.md

**Environment:** SQLite `3.53.4`, Python `____`, OS `Windows`

## 1. References
- SQLite query plans: https://www.sqlite.org/eqp.html
- Why an index gets ignored: https://use-the-index-luke.com/
- SQL injection: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- Relational algebra: https://en.wikipedia.org/wiki/Relational_algebra

## 2. What I googled
- "sqlite with recursive example" -> showed me some common table expressions
- "sqlite WITH RECURSIVE generate numbers" -> it builds rows 1..N from one starting row
- "sqlite why is my index not used" -> the planner skips an index when most rows match, or when a function wraps the column.
- "sql injection bound parameters vs escaping" -> parameters send the query and the value separately, so the value can never be read as SQL.

## 3. Predictions vs reality

### Task A: plan safari (stand-in legacy.db, 20,000 jobs)
| Query | My prediction | Actual plan | Why |
|---|---|---|---|
| `maint_job WHERE technician='Beier'` | Scaning for a specific name | `SCAN maint_job` | no index yet |
| `machine WHERE machine_name='cnc-02'` | Checks for a specific machine name or id? | `SCAN machine` | `machine_name` is not a key or indexed |
| `maint_job WHERE technician LIKE '%ei%'` | More wider scan than a specific name like "Beier" | `SCAN maint_job` | leading `%`: nothing to start from |
| after `ix_job_tech`: `technician='Beier'` | We find the specifc result | `SEARCH maint_job USING INDEX ix_job_tech (technician=?)` | index matches the filter |
| after `ix_job_tech`: `LIKE '%ei%'` | We have more filtered results | `SCAN maint_job` | a sorted index can't help a leading wildcard |
| after `ix_job_tech`: `machine_name='cnc-02'` | very specific ID search | `SCAN machine` | index is on another table |
| after `ix_job_tech`: `lower(technician)='beier'` | on a list, finds the lower bound | `SCAN maint_job` | function wraps the column |

## 4. Surprises
- Without any extra index the engine still starts from the biggest table (`order_line`) and reaches the other three through their primary keys.
- Adding `ix_orderline_order` changed the plan but made the dashboard about 3x **slower**.
- SQLite accepts a `SELECT` alias inside `WHERE`, which the class calls an error. (Other databases reject it.)
- `date(ordered_on)=...` still scans even with an index, but it scans the smaller index instead of the table.
- Two identical runs gave different times (100 ms vs 118 ms), so the plan is better evidence than the clock.

## 5. LLM answers I verified

### Task 1
**Prompt (exact):**
> SQLite schema: `customer(customer_id, name, city)`, `product(product_id, sku, price)`, `orders(order_id, customer_id, ordered_on, status)`, `order_line(order_id, product_id, qty)`. Write a query that returns, for each city, the number of distinct customers and the total revenue (sum of `qty*price`) of orders placed in 2025, ordered by revenue descending.

**LLM SQL:**
```sql
SELECT c.city,
       COUNT(DISTINCT c.customer_id) AS customers,
       SUM(ol.qty * p.price)         AS revenue
FROM customer c
JOIN orders o      ON o.customer_id = c.customer_id
JOIN order_line ol ON ol.order_id   = o.order_id
JOIN product p     ON p.product_id  = ol.product_id
WHERE o.ordered_on >= '2025-01-01' AND o.ordered_on < '2026-01-01'
GROUP BY c.city
ORDER BY revenue DESC;
```
**Result:** Bielefeld 500 / 11,242,176.0 · Gütersloh 500 / 8,422,344.0 · Münster 500 / 5,493,504.0 · Paderborn 500 / 2,815,656.0

**Actual plan:** see `task1_plan.txt`.

**Correctness check (sentence):** The query runs and is correct: I recomputed the same four cities independently in Python and got identical customers and revenue. `COUNT(DISTINCT ...)` is needed because the joins repeat each customer once per order line. The date range uses `>= ... AND < ...`; `BETWEEN '2025-01-01' AND '2026-01-01'` would wrongly include 2026-01-01 and count 40,686 orders instead of 40,575. A common LLM variant, `strftime('%Y', ordered_on) = '2025'`, wraps the column in a function and stops the index being used for a range search.

### Task 2: LLM "optimize" answer
**LLM reply (summary):** "Add indexes on the filter and join columns: `orders(ordered_on)` for the date filter, `order_line(order_id)` for the join to orders, `order_line(product_id)` for the join to product."

**Tested one at a time (median of 5 runs, my machine):**
| Index added | Dashboard plan | Dashboard time | Verdict |
|---|---|---|---|
| none (baseline) | `SCAN ol` first | ~100–118 ms | |
| `ix_orders_ordered_on` | unchanged | ~100–120 ms | not used by this query |
| `ix_orderline_order` | flips to `SEARCH o USING INDEX ix_orders_ordered_on` then `SEARCH ol USING INDEX ix_orderline_order` | ~340–370 ms | plan changed, **slower** |
| `ix_orderline_product` | unchanged from previous | ~330–340 ms | not used by this query |

**Where the indexes do help:**
| Query | Before | After |
|---|---|---|
| `WHERE ordered_on='2026-02-14'` | `SCAN o`, ~2 ms | `SEARCH o USING INDEX ix_orders_ordered_on (ordered_on=?)`, ~0.1 ms |
| `WHERE ol.product_id=42` | `SCAN ol`, ~7 ms | `SEARCH ol USING INDEX ix_orderline_product (product_id=?)`, ~0.6 ms |

**Conclusion:** the LLM's list was not wrong, but it was incomplete advice: an index helps *specific queries*. `ix_orderline_product` is useless for the dashboard (the planner reaches `product` by primary key) but useful for a `product_id` filter. For the dashboard, `ix_orderline_order` makes things worse because the 2025 filter keeps about two thirds of all orders, so many index lookups cost more than one sequential scan.

**Negative result:** `WHERE date(ordered_on) = ...` stays a `SCAN` (it becomes `SCAN orders USING COVERING INDEX`), because the function hides the column from the index.

### Pod questions I asked an LLM (and what I verified by running)
- *Relational algebra, briefly:* algebra is the meaning, SQL is the syntax. σ = WHERE (pick rows), π = SELECT list (pick columns), ⋈ = JOIN, γ = GROUP BY + aggregates. To explain it to a peer: "σ filters rows, π keeps columns, ⋈ glues tables."
- *Why FROM before SELECT?* SQL must know which rows exist before it can pick columns. Verified: an aggregate in `WHERE` fails with `misuse of aggregate: COUNT()`, and `WHERE` after `GROUP BY` is a syntax error; the fix is `HAVING`.
- *Covering index:* when the index holds every column the query needs, the table is never opened. Verified: `SELECT a ... WHERE a=1` gives `SEARCH ... USING COVERING INDEX`; `SELECT a, b ...` gives plain `USING INDEX`.
- *Why can't an index help `LIKE '%ei%'`?* An index is sorted from the left; a leading wildcard gives no starting point. Verified: still `SCAN`.

## 6. Algebra check (Task B / Task 4)
Query: `SELECT o.order_id, o.ordered_on, c.name FROM orders o JOIN customer c ON c.customer_id = o.customer_id WHERE o.ordered_on = '2026-02-14';`

**Mine (write yours first, then compare):**
`π_{order_id, ordered_on, name}( σ_{ordered_on='2026-02-14'}( orders ⋈_{customer_id=customer_id} customer ) )`

**LLM's:**
`π_{o.order_id, o.ordered_on, c.name}( σ_{o.ordered_on='2026-02-14'}( ρ_o(orders) ⋈_{o.customer_id=c.customer_id} ρ_c(customer) ) )`

**Diff:** same meaning. The LLM adds the renames ρ for the aliases `o` and `c`. A third equivalent form applies σ to `orders` *before* the join, which is what the optimizer prefers (filter early, join fewer rows). Mapping check: σ=WHERE, π=SELECT list, ⋈=JOIN...ON, ρ=AS. SQL and algebra match.

**Dashboard query (extended algebra, γ = grouping):**
`γ_{c.city; COUNT(DISTINCT c.customer_id)→customers, SUM(ol.qty·p.price)→revenue}( σ_{o.ordered_on ≥ '2025-01-01' ∧ o.ordered_on < '2026-01-01'}( ((c ⋈ o) ⋈ ol) ⋈ p ) )`, then sort by revenue descending.

## 7. Escaping vs parameters (Task 3)
**Payload used:** `' OR '1'='1` (returned all 2,000 customers). The story's apostrophe crash reproduced with `O'Brien` → `OperationalError: near "Brien": syntax error`. The safe version returned `[]` for both.

**Why escaping is not a real fix:** Escaping tries to block one bad character, and I would have to predict every dangerous input in every place. It does not work for table or column names, and numbers need no quote at all (`WHERE id = 1 OR 1=1`). Encodings and different databases treat characters differently, so a hand-made filter breaks. And I, the developer, stay responsible for getting it right on every single call. With bound parameters the database receives the query and the value separately, so the value is always just data and can never be read as SQL.

## 8. Curiosities (with sources)
| What looks odd | Source |
|---|---|
| `date('2025-01-01','+'\|\|(x%540)\|\|' days')` builds the modifier as a string | `setup.sql`, line (4) |
| `date()` repeats after 540 days (x=540 gives 2025-01-01 again) | `setup.sql` + `SELECT MIN(ordered_on), MAX(ordered_on)...` |
| The plan has a separate `USE TEMP B-TREE FOR count(DISTINCT)` | `task1_plan.txt` |
| `SELECT` alias works in `WHERE` in SQLite (class says it should not) | Module 3 "six clauses" text vs my test |
| Correlated subquery took ~3.9 s but ~3 ms with an index on `orders(customer_id, status)` | Task 5 |
| Every `orders.customer_id` exists, but nothing enforces it (Module 4 foreign keys) | `setup.sql` line (3) |
| "I don't know what this does": `WITH RECURSIVE ... INSERT` placed before the INSERT | `setup.sql` |

## 9. Stretcher (Task 5): late orders per customer
| Version | Median | Rows | Plan |
|---|---:|---:|---|
| GROUP BY (what the LLM gives by default) | ~6 ms | 400 | `SCAN o`, `SEARCH c`, temp B-trees |
| Correlated subquery | ~3,900 ms | 2000 | `SCAN c` + `CORRELATED SCALAR SUBQUERY` → `SCAN o` once per customer |
| Window `COUNT(*) OVER (PARTITION BY ...)` | ~14 ms | 400 | co-routines + `DISTINCT` + extra temp B-trees |

GROUP BY is the most readable and fastest. The subquery returns 2000 rows (1600 customers with 0 late orders), so it is not equivalent. The window version needs `DISTINCT`, otherwise it returns one row per order.

## 10. Posted to #sql-questions
- "Module 3: why does `date(ordered_on) = ...` become `SCAN ... USING COVERING INDEX` instead of a plain `SCAN` once an index exists?"
- "Module 3: SQLite accepts a SELECT alias in WHERE but the class says it's wrong. Is this SQLite-only?"
