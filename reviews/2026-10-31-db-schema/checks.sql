-- Evidence queries for 01-findings.md. Run against a fresh build:
--   uv run python build.py
--   sqlite3 cert_basis.sqlite < reviews/2026-10-31-db-schema/checks.sql
.headers on
.mode column

.print
.print '== F-01: rows per TCDS line (should be 1 per line in target model)'
SELECT tcb_id, display_order, count(*) AS rows_per_line
FROM cert_basis_entries GROUP BY 1, 2;

.print
.print '== F-02: provisions resolved to more than one version within one TCB'
SELECT cbe.tcb_id, sa.regulation_id, count(DISTINCT sa.id) AS versions
FROM cert_basis_entries cbe
JOIN section_amendments sa ON sa.id = cbe.section_amendment_id
GROUP BY 1, 2 HAVING versions > 1;

.print
.print '== F-06: distinct actions per amendment vs sections carrying them'
SELECT a.designator,
       count(DISTINCT sa.id) AS sections,
       count(DISTINCT aa.type || '|' || ifnull(aa.reference, '') || '|' || ifnull(aa.issued_on, '')) AS distinct_actions,
       count(*) AS action_rows
FROM amendment_actions aa
JOIN section_amendments sa ON sa.id = aa.section_amendment_id
JOIN amendments a ON a.id = sa.amendment_id
GROUP BY 1 ORDER BY a.part_id, a.ordinal;

.print
.print '== F-07: sentinel values'
SELECT 'Initial Adoption cite' AS sentinel, count(*) FROM section_amendments WHERE federal_register_cite = 'Initial Adoption'
UNION ALL
SELECT 'TEXT MISSING', count(*) FROM section_amendments WHERE text = 'TEXT MISSING';

.print
.print '== F-09: parts with NULL title_number (UNIQUE not enforced for these)'
SELECT id, part FROM regulation_parts WHERE title_number IS NULL;

.print
.print '== F-14: implausible or malformed dates'
SELECT 'amendment_actions.issued_on' AS col, issued_on AS value FROM amendment_actions
 WHERE issued_on IS NOT NULL AND (date(issued_on) IS NOT issued_on OR issued_on > date('now'))
UNION ALL
SELECT 'amendments.effective_date', effective_date FROM amendments
 WHERE date(effective_date) IS NOT effective_date OR effective_date > date('now')
UNION ALL
SELECT 'tcds.revision_date', revision_date FROM tcds
 WHERE revision_date IS NOT NULL AND date(revision_date) IS NOT revision_date;

.print
.print '== F-19: index list'
SELECT tbl_name, name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL;

.print
.print '== F-20: user_version (0 = unversioned)'
PRAGMA user_version;

.print
.print '== F-26: FR cite coverage'
SELECT federal_register_cite IS NULL AS cite_missing, count(*) FROM section_amendments GROUP BY 1;
