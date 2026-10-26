-- =============================================================================
-- sql/20_site.sql
-- Project : Non-Profit Spending Reports
-- Date    : 2026-10-26
-- Purpose : Build the "site" schema the pages are rendered from:
--           - org:    each organization's most recent return, its size rank,
--                     salary base and how much of it the top 10 listed get
--           - role:   everyone listed on those returns
--           - person: people (by normalized name) at organizations with pages
-- Usage   : psql -v rank_by=revenue -v min_usd=10000000 -f sql/20_site.sql
-- Change log:
--   2026-10-26  0.1.0  Initial version.
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

UPDATE site.org SET has_page = coalesce(measure, 0) >= :min_usd;

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
CREATE INDEX ON site.role (key);

UPDATE site.org o SET listed_count = s.n, board_count = s.nb,
       top10_comp = s.top10, listed_comp = s.total
FROM (SELECT ein, count(*) AS n, count(*) FILTER (WHERE board) AS nb,
             sum(total_comp) FILTER (WHERE pay_rank <= 10) AS top10,
             sum(total_comp) AS total
      FROM site.role GROUP BY ein) s
WHERE s.ein = o.ein;

-- People with a page: anyone listed by an organization that has a page.
CREATE TABLE site.person AS
SELECT key,
       (array_agg(r.name ORDER BY o.measure DESC NULLS LAST))[1] AS name,
       count(DISTINCT r.ein) AS org_count,
       sum(r.total_comp) AS total_comp
FROM site.role r JOIN site.org o USING (ein)
WHERE r.key IS NOT NULL
  AND r.key IN (SELECT r2.key FROM site.role r2 JOIN site.org o2 USING (ein)
                WHERE o2.has_page AND r2.key IS NOT NULL)
GROUP BY key;
ALTER TABLE site.person ADD PRIMARY KEY (key);

ANALYZE site.org;
ANALYZE site.role;
ANALYZE site.person;
