<!--
  CHANGELOG.md
  Project : Non-Profit Spending Reports
  Date    : 2026-10-26
  Purpose : Release history, following Keep a Changelog and SemVer.
  Change log:
    2026-10-26  0.1.0  Created.
-->

# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Project scaffold following the Campaign Donations project.
- `scripts/fetch.sh`: download IRS Form 990 series e-file XML (TEOS) and the EO BMF.
- Safe XML parser (defusedxml) for Forms 990, 990-EZ and 990-PF: filer, revenue,
  expenses, assets, salary base, employees, and everyone listed in Part VII.
- Person name matching across organizations by normalized first and last name.
- `nppipe extract` (parallel) and `scripts/load.sh` to load PostgreSQL.
- `sql/20_site.sql`: latest return per organization, size rank, top 10 pay share.
- Static site: home page with search and top 100, organization, person, A to Z
  and about pages; client-side search over static JSON.
- Feature flags in `config/flags.toml` with `NP_*` environment overrides, including
  Phase 2 and Phase 3 switches (off).
- Security headers via `.htaccess` and a Content-Security-Policy meta tag.
