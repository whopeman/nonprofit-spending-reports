<!--
  README.md
  Project : Non-Profit Spending Reports
  Date    : 2026-10-26
  Purpose : Overview, data sources, setup, build, test and deploy instructions.
  Change log:
    2026-10-26  0.1.0  Created.
-->

# Non-Profit Spending Reports

Who runs the largest US non-profits, and who gets paid, from the public returns
they file with the IRS. Planned home: <https://hopemanhorde.com/nonprofit-spending/>.

The site is static HTML with one small search script:

- **Home**: search box and the top 100 organizations by total revenue.
- **Organization pages**: revenue, expenses, assets, salary base and employees; the
  10 best-paid people listed and their share of the salary base; board members;
  everyone else listed; links to the filing.
- **Person pages**: every organization whose latest return lists that name, with
  title, role, hours and pay.
- **A to Z** pages, so everything can be reached without JavaScript.

## Phases

| Phase | What                                                                 | Flag                |
| ----- | -------------------------------------------------------------------- | ------------------- |
| 1     | Searchable site, top 100, org and person pages (this release)        | always on           |
| 2     | Charitable (program) spending versus internal costs                  | `phase2_spending`   |
| 3     | Public-source review of possible violations of exempt status         | `phase3_violations` |

## Data sources

All bulk downloads from the IRS; no API calls or scraping.

| Source | What it gives | Link |
| ------ | ------------- | ---- |
| Form 990 series e-file XML (TEOS) | Every e-filed Form 990, 990-EZ, 990-PF and 990-T, monthly zips by processing year (2019 on), with an index CSV per year | <https://www.irs.gov/charities-non-profits/form-990-series-downloads> |
| EO Business Master File | Every recognized exempt organization: NTEE category, subsection, ruling date | <https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf> |
| SOI annual extracts (not used yet) | Selected financial fields from 990, 990-EZ, 990-PF as flat files | <https://www.irs.gov/statistics/soi-tax-stats-annual-extract-of-tax-exempt-organization-financial-data> |

Notes on the sources:

- The IRS moved this data off AWS to TEOS at the end of 2021
  ([IRS news release](https://www.irs.gov/newsroom/irs-makes-tax-exempt-organization-search-primary-source-to-get-exempt-organization-data),
  [AWS registry notice](https://registry.opendata.aws/irs990/)).
- Form 990-T (unrelated business income) is in the XML for 501(c)(3) organizations,
  whose 990-T returns are public ([IRS](https://www.irs.gov/node/10355)).
  It is downloaded but not parsed in Phase 1.
- Form 990 Part VII and Schedule J define who is listed and how pay is reported
  ([IRS Part VII and Schedule J](https://www.irs.gov/node/6094)).

## How it works

| Step    | Where                 | What                                                      |
| ------- | --------------------- | --------------------------------------------------------- |
| Fetch   | WSL, `scripts/`       | Download XML zips and BMF to `~/np-data` (about 15 GB)    |
| Extract | WSL, Python           | Parse every return in parallel into TSV files              |
| Load    | WSL, PostgreSQL       | COPY into `raw`, build the `site` schema (`sql/`)          |
| Render  | WSL, Python           | Jinja2 templates to static HTML in `site/`                 |
| Deploy  | Windows, PowerShell   | Framework deploy script uploads `site/` over SFTP          |

## Layout

| Path                | What it holds                                         |
| ------------------- | ----------------------------------------------------- |
| `config/flags.toml` | Feature flags                                         |
| `src/nppipe/`       | Python package: parser, extract, names, renderer, CLI |
| `templates/`        | Jinja2 page templates                                 |
| `static/`           | CSS, search script and `.htaccess` (security headers) |
| `sql/`              | Database tables and site schema SQL                   |
| `scripts/`          | Fetch and load scripts (bash, run in WSL)             |
| `tests/`            | pytest suite and made-up XML fixtures                 |

## Prerequisites

- WSL (Ubuntu) with PostgreSQL 16+ and a role for your user that can create databases.
- [uv](https://docs.astral.sh/uv/) in WSL for Python (3.12+).
- Node.js 20+ for HTML validation.
- About 60 GB free in WSL for the zips, work files and database.

## Setup and build

```sh
# WSL, in the repo folder
export UV_PROJECT_ENVIRONMENT=~/venvs/np   # keep the venv off the Windows drive
uv sync
scripts/fetch.sh all                        # about 15 GB
scripts/load.sh all                         # extract, load, build the site schema
uv run nppipe demo                          # layout check with made-up data
uv run nppipe build                         # the real site, from PostgreSQL
```

## Test and lint

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pip-audit
npm install && npm run lint:html
```

## Feature flags

Set in `config/flags.toml`, or override per run with `NP_<NAME>`, for example
`NP_TOP_N=250 uv run nppipe build`.

| Flag                | Default            | Effect                                              |
| ------------------- | ------------------ | --------------------------------------------------- |
| `use_gpu`           | `true`             | GPU fuzzy person matching (Phase 2; unused in 0.1)  |
| `filing_years`      | 2023 to 2026       | IRS processing years of XML to load                 |
| `rank_by`           | `revenue`          | `revenue`, `expenses` or `assets`                   |
| `top_n`             | `100`              | Organizations in the home page list                 |
| `org_page_min_usd`  | `10000000`         | Organizations below this get no page of their own   |
| `phase2_spending`   | `false`            | Show program spending versus internal costs         |
| `phase3_violations` | `false`            | Show the violations review                          |

## Deploy

Copy `deploy.example.json` to `deploy.local.json` (gitignored) and set `user`
and `keyPath`. Then, from the `Framework_Website_HopemanHorde` repo:

```sh
npm run deploy -- -ConfigPath ../nonprofit-spending-reports/deploy.local.json            # dry run
npm run deploy -- -ConfigPath ../nonprofit-spending-reports/deploy.local.json -Execute   # upload
```

## Caveats

- People are matched by name only (first and last), so different people with the
  same name share a page. Every person page says so.
- Figures are as filed with the IRS and are not audited here.

## Contributing

Issues and comments are limited to collaborators.

## License

Code: [MIT](LICENSE). IRS data is public domain.
