#!/usr/bin/env bash
# =============================================================================
# scripts/load.sh
# Project : Non-Profit Spending Reports
# Date    : 2026-10-26
# Purpose : Parse the downloaded IRS XML into TSV files, load them and the
#           EO BMF into PostgreSQL (database $NP_DB, default "nonprofit"),
#           and build the "site" schema the pages are made from.
# Usage   : (WSL) scripts/load.sh [init|extract|raw|site|all]
# Needs   : a PostgreSQL role for the current user with CREATEDB, and
#           UV_PROJECT_ENVIRONMENT pointing at the project venv.
# Change log:
#   2026-10-26  0.1.0  Initial version.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${NP_DATA:-$HOME/np-data}"
WORK="$DATA/work"
DB="${NP_DB:-nonprofit}"
step="${1:-all}"
log() { echo "$(date -Is) $*"; }
psql_db() { psql -X -q -v ON_ERROR_STOP=1 -d "$DB" "$@"; }
flag() { (cd "$HERE" && uv run --quiet python -c "from nppipe.flags import load_flags; print(load_flags().$1)"); }

init() {
  log "init database $DB"
  psql -X -q -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$DB'" | grep -q 1 \
    || createdb "$DB"
}

extract() {
  log "extract XML to $WORK"
  (cd "$HERE" && uv run nppipe extract --data "$DATA" --work "$WORK")
}

raw() {
  log "load raw tables"
  psql_db -f "$HERE/sql/10_raw.sql"
  for f in "$WORK"/*.filing.tsv; do
    y="$(basename "$f" | cut -c1-4)"
    psql_db -c "\\copy raw.filing FROM '$f'" 2>&1 | sed "s|^|$y |"
  done
  for f in "$WORK"/*.person.tsv; do
    psql_db -c "\\copy raw.person FROM '$f'"
  done
  for r in 1 2 3 4; do
    psql_db -c "\\copy raw.bmf FROM '$DATA/bmf/eo$r.csv' WITH (FORMAT csv, HEADER true)"
  done
  psql_db -f "$HERE/sql/15_dedupe.sql"
  psql_db -Atc "SELECT form, count(*) FROM raw.filing GROUP BY 1 ORDER BY 1"
}

site() {
  local rank_by min_usd page_by top_pct top_n
  rank_by="$(flag rank_by)"
  min_usd="$(flag org_page_min_usd)"
  page_by="$(flag page_by)"
  top_pct="$(flag page_top_pct)"
  top_n="$(flag top_n)"
  log "build site schema (rank by $rank_by; pages: top $top_pct% by $page_by of orgs from \$$min_usd)"
  psql_db -v rank_by="$rank_by" -v min_usd="$min_usd" -v page_by="$page_by" \
    -v top_pct="$top_pct" -v top_n="$top_n" -f "$HERE/sql/20_site.sql"
  psql_db -Atc "SELECT 'orgs with pages', count(*) FROM site.org WHERE has_page
                UNION ALL SELECT 'people with pages', count(*) FROM site.person"
}

case "$step" in
  init) init ;;
  extract) extract ;;
  raw) raw ;;
  site) site ;;
  all) init; extract; raw; site ;;
  *) echo "usage: $0 [init|extract|raw|site|all]" >&2; exit 2 ;;
esac
log "done $step"
