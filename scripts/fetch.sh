#!/usr/bin/env bash
# =============================================================================
# scripts/fetch.sh
# Project : Non-Profit Spending Reports
# Date    : 2026-10-26
# Purpose : Download the public IRS data the site is built from into
#           $NP_DATA (default ~/np-data). Resumable; safe to re-run.
#           - Form 990 series e-file XML (TEOS bulk downloads), by the year
#             the IRS processed the filing, with each year's index CSV
#           - Exempt Organizations Business Master File (EO BMF), 4 regions
# Usage   : (WSL) scripts/fetch.sh [xml|bmf|all] [years...]
#           scripts/fetch.sh xml 2025 2026
# Change log:
#   2026-10-26  0.1.0  Initial version.
#   2026-10-28  0.1.0  A zip counts as downloaded when its central directory
#                      reads; "zipfile -t" failed on every Deflate64 batch, so
#                      curl re-requested them and exited 33, stopping the run
#                      (torch).
# =============================================================================
set -euo pipefail

DATA="${NP_DATA:-$HOME/np-data}"
XML="https://apps.irs.gov/pub/epostcard/990/xml"
LIST="https://www.irs.gov/charities-non-profits/form-990-series-downloads"
BMF="https://www.irs.gov/pub/irs-soi"
what="${1:-all}"
shift || true
years=("$@")
[ ${#years[@]} -eq 0 ] && years=(2023 2024 2025 2026)

get() {  # get <url> <dest>
  echo "$(date -Is) get $1"
  curl -fsS -L -C - --retry 10 --retry-delay 30 -o "$2" "$1"
}

if [ "$what" = xml ] || [ "$what" = all ]; then
  page="$(curl -fsS -L "$LIST")"
  for y in "${years[@]}"; do
    mkdir -p "$DATA/xml/$y"
    # The index grows as the IRS adds batches, so always fetch it fresh.
    rm -f "$DATA/xml/$y/index_$y.csv"
    get "$XML/$y/index_$y.csv" "$DATA/xml/$y/index_$y.csv"
    # Batch names come from the download page (only ${y}_TEOS_XML_*.zip).
    for f in $(grep -oE "${y}_TEOS_XML_[0-9A-Z]+\.zip" <<<"$page" | sort -u); do
      # A finished zip has its central directory (written last) and is not
      # fetched again. Members are not decompressed here: the standard library
      # cannot read Deflate64, and extract checks every member's CRC anyway.
      if [ -s "$DATA/xml/$y/$f" ] && python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).close()' \
          "$DATA/xml/$y/$f" >/dev/null 2>&1; then
        continue
      fi
      get "$XML/$y/$f" "$DATA/xml/$y/$f"
    done
  done
fi

if [ "$what" = bmf ] || [ "$what" = all ]; then
  mkdir -p "$DATA/bmf"
  for r in 1 2 3 4; do
    rm -f "$DATA/bmf/eo$r.csv"
    get "$BMF/eo$r.csv" "$DATA/bmf/eo$r.csv"
  done
fi
echo "$(date -Is) done"
