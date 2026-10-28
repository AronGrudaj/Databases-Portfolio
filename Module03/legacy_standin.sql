-- STAND-IN for Module 2's legacy.db (generated with an LLM, as allowed by the professor).
-- Same table/column names that Task A uses: machine(machine_name), maint_job(technician).
DROP TABLE IF EXISTS maint_job;
DROP TABLE IF EXISTS machine;

CREATE TABLE machine(machine_id INTEGER PRIMARY KEY, machine_name TEXT NOT NULL, line TEXT NOT NULL);
CREATE TABLE maint_job(job_id INTEGER PRIMARY KEY, machine_id INTEGER NOT NULL,
                       technician TEXT NOT NULL, done_on TEXT NOT NULL);

-- 20 machines: cnc-01 ... cnc-20
WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x < 20)
INSERT INTO machine(machine_id, machine_name, line)
  SELECT x, 'cnc-' || printf('%02d', x), CASE x % 2 WHEN 0 THEN 'Line A' ELSE 'Line B' END FROM n;

-- 20,000 maintenance jobs, 6 technicians
WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x < 20000)
INSERT INTO maint_job(job_id, machine_id, technician, done_on)
  SELECT x, (x % 20) + 1,
         CASE x % 6 WHEN 0 THEN 'Beier' WHEN 1 THEN 'Meier' WHEN 2 THEN 'Seidel'
                    WHEN 3 THEN 'Krause' WHEN 4 THEN 'Weiss' ELSE 'Neumann' END,
         date('2025-01-01', '+' || (x % 365) || ' days')
  FROM n;
