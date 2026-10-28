-- =============================================================================
-- sql/20_site.sql
-- Project : Non-Profit Spending Reports
-- Date    : 2026-10-26
-- Purpose : Build the "site" schema the pages are rendered from:
--           - org:    each organization's most recent return, its size rank,
--                     salary base and how much of it the top 10 listed get
--           - role:   everyone listed on those returns (pages show only
--                     leadership and the top 10 paid)
-- Usage   : psql -v rank_by=revenue -v min_usd=10000000 -v page_by=assets
--                -v top_pct=10 -v top_n=100 -f sql/20_site.sql
-- Change log:
--   2026-10-26  0.1.0  Initial version.
--   2026-10-26  0.1.0  Pages only for the top top_pct percent by page_by.
--   2026-10-28  0.1.0  No person table: the site has no person pages.
-- =============================================================================
\set ON_ERROR_STOP on
DROP SCHEMA IF EXISTS site CASCADE;
CREATE SCHEMA site;

-- Most recent tax period per EIN. For the same period, the return filed last
-- (highest object id, e.g. an amended return) wins.
CREATE TABLE site.org AS
SELECT DISTINCT ON (f.ein) f.*
FROM raw.filing f
WHERE f.ein ~ '^[0-9]{9}$'
ORDER BY f.ein, f.tax_period_end DESC NULLS LAST, f.object_id DESC;

ALTER TABLE site.org ADD PRIMARY KEY (ein);
ALTER TABLE site.org
  ADD COLUMN measure bigint,
  ADD COLUMN rank int,
  ADD COLUMN has_page boolean,
  ADD COLUMN ntee_cd text,
  ADD COLUMN subsection text,
  ADD COLUMN listed_count int,
  ADD COLUMN board_count int,
  ADD COLUMN top10_comp bigint,
  ADD COLUMN listed_comp bigint;

UPDATE site.org o SET ntee_cd = b.ntee_cd, subsection = b.subsection
FROM (SELECT DISTINCT ON (ein) ein, ntee_cd, subsection FROM raw.bmf ORDER BY ein) b
WHERE b.ein = o.ein;

UPDATE site.org SET measure = CASE :'rank_by'
  WHEN 'expenses' THEN expenses WHEN 'assets' THEN assets ELSE revenue END;

UPDATE site.org o SET rank = r.rn
FROM (SELECT ein, row_number() OVER (ORDER BY measure DESC NULLS LAST, ein) AS rn
      FROM site.org) r
WHERE r.ein = o.ein;

-- Pages: among organizations whose measure reaches min_usd, the top top_pct
-- percent by page_by; plus the home page top list (rank <= top_n).
WITH eligible AS (
  SELECT ein, CASE :'page_by' WHEN 'revenue' THEN revenue WHEN 'expenses' THEN expenses
                ELSE assets END AS value
  FROM site.org WHERE coalesce(measure, 0) >= :min_usd
), cut AS (
  SELECT ein FROM eligible ORDER BY value DESC NULLS LAST, ein
  LIMIT ceil((SELECT count(*) FROM eligible) * :top_pct / 100.0)
)
UPDATE site.org o SET has_page = (o.rank <= :top_n OR o.ein IN (SELECT ein FROM cut));

-- Everyone listed on each organization's latest return.
CREATE TABLE site.role AS
SELECT o.ein, p.seq, p.name, p.key, p.title, p.hours, p.board, p.officer,
       p.key_employee, p.highest_comp, p.former,
       coalesce(p.comp_org, 0) AS comp_org, coalesce(p.comp_related, 0) AS comp_related,
       coalesce(p.comp_other, 0) AS comp_other,
       coalesce(p.comp_org, 0) + coalesce(p.comp_related, 0) + coalesce(p.comp_other, 0)
         AS total_comp,
       row_number() OVER (PARTITION BY o.ein ORDER BY
         coalesce(p.comp_org, 0) + coalesce(p.comp_related, 0) + coalesce(p.comp_other, 0) DESC,
         p.seq) AS pay_rank
FROM site.org o JOIN raw.person p ON p.object_id = o.object_id;
CREATE INDEX ON site.role (ein);

UPDATE site.org o SET listed_count = s.n, board_count = s.nb,
       top10_comp = s.top10, listed_comp = s.total
FROM (SELECT ein, count(*) AS n, count(*) FILTER (WHERE board) AS nb,
             sum(total_comp) FILTER (WHERE pay_rank <= 10) AS top10,
             sum(total_comp) AS total
      FROM site.role GROUP BY ein) s
WHERE s.ein = o.ein;

ANALYZE site.org;
ANALYZE site.role;
