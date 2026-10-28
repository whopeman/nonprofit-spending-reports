-- =============================================================================
-- sql/15_dedupe.sql
-- Project : Non-Profit Spending Reports
-- Date    : 2026-10-26
-- Purpose : The IRS sometimes publishes the same return in more than one
--           batch zip (for example 2025_TEOS_XML_05A and 05B). Keep one copy
--           of each return and its people, then add the keys and indexes.
-- Usage   : psql -d nonprofit -f sql/15_dedupe.sql   (scripts/load.sh runs it)
-- Change log:
--   2026-10-26  0.1.0  Initial version.
--   2026-10-28  0.1.0  Drop leftovers of a run that stopped part way (torch).
-- =============================================================================
\set ON_ERROR_STOP on

DROP TABLE IF EXISTS raw.filing_dedup, raw.person_dedup;
CREATE TABLE raw.filing_dedup AS
SELECT DISTINCT ON (object_id) * FROM raw.filing ORDER BY object_id, source_year DESC;
DROP TABLE raw.filing;
ALTER TABLE raw.filing_dedup RENAME TO filing;
ALTER TABLE raw.filing ADD PRIMARY KEY (object_id);
CREATE INDEX ON raw.filing (ein);

CREATE TABLE raw.person_dedup AS
SELECT DISTINCT ON (object_id, seq) * FROM raw.person ORDER BY object_id, seq;
DROP TABLE raw.person;
ALTER TABLE raw.person_dedup RENAME TO person;
ALTER TABLE raw.person ADD PRIMARY KEY (object_id, seq);

ANALYZE raw.filing;
ANALYZE raw.person;
ANALYZE raw.bmf;
