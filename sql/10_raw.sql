-- =============================================================================
-- sql/10_raw.sql
-- Project : Non-Profit Spending Reports
-- Date    : 2026-10-26
-- Purpose : Tables for the parsed IRS e-file returns (filled by COPY from the
--           TSV files nppipe extract writes) and the EO Business Master File.
-- Usage   : psql -d nonprofit -f sql/10_raw.sql   (scripts/load.sh runs it)
-- Change log:
--   2026-10-26  0.1.0  Initial version.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS raw;

DROP TABLE IF EXISTS raw.filing CASCADE;
CREATE TABLE raw.filing (
  object_id         text NOT NULL,
  ein               text NOT NULL,
  name              text,
  city              text,
  state             text,
  form              text NOT NULL,
  tax_year          int,
  tax_period_end    date,
  amended           boolean,
  revenue           bigint,
  expenses          bigint,
  assets            bigint,
  program_expenses  bigint,
  salaries          bigint,
  comp_and_benefits bigint,
  employees         int,
  website           text,
  mission           text,
  source_year       int NOT NULL
);

DROP TABLE IF EXISTS raw.person CASCADE;
CREATE TABLE raw.person (
  object_id    text NOT NULL,
  seq          int NOT NULL,
  name         text NOT NULL,
  key          text,
  title        text,
  hours        numeric,
  board        boolean,
  officer      boolean,
  key_employee boolean,
  highest_comp boolean,
  former       boolean,
  comp_org     bigint,
  comp_related bigint,
  comp_other   bigint
);

-- EO BMF: https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf
DROP TABLE IF EXISTS raw.bmf CASCADE;
CREATE TABLE raw.bmf (
  ein text, name text, ico text, street text, city text, state text, zip text,
  "group" text, subsection text, affiliation text, classification text, ruling text,
  deductibility text, foundation text, activity text, organization text, status text,
  tax_period text, asset_cd text, income_cd text, filing_req_cd text,
  pf_filing_req_cd text, acct_pd text, asset_amt bigint, income_amt bigint,
  revenue_amt bigint, ntee_cd text, sort_name text
);
