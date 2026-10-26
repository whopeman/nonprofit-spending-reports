"""
src/nppipe/extract.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Turn the downloaded TEOS batch zips into tab-separated files that
          PostgreSQL loads with COPY: <batch>.filing.tsv and <batch>.person.tsv
          in the work folder. Batches run in parallel, one process each.
          A batch whose output is newer than its zip is skipped.
Usage   : extract_all(data_dir, work_dir, years=(2025,), jobs=8)
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import os
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from nppipe.parse990 import Filing, iter_zip

FILING_COLS = (
    "object_id",
    "ein",
    "name",
    "city",
    "state",
    "form",
    "tax_year",
    "tax_period_end",
    "amended",
    "revenue",
    "expenses",
    "assets",
    "program_expenses",
    "salaries",
    "comp_and_benefits",
    "employees",
    "website",
    "mission",
)
PERSON_COLS = (
    "object_id",
    "seq",
    "name",
    "key",
    "title",
    "hours",
    "board",
    "officer",
    "key_employee",
    "highest_comp",
    "former",
    "comp_org",
    "comp_related",
    "comp_other",
)


def _cell(v) -> str:
    """COPY text format: \\N for null, and no tabs, newlines or backslashes in values."""
    if v is None:
        return r"\N"
    if isinstance(v, bool):
        return "t" if v else "f"
    return str(v).replace("\\", "/").replace("\t", " ").replace("\n", " ").replace("\r", " ")


def filing_row(f: Filing, source_year: int) -> list[str]:
    return [_cell(getattr(f, c)) for c in FILING_COLS] + [str(source_year)]


def person_rows(f: Filing) -> list[list[str]]:
    rows = []
    for i, p in enumerate(f.people):
        vals = [
            f.object_id,
            i,
            p.name,
            p.key,
            p.title,
            p.hours,
            p.board,
            p.officer,
            p.key_employee,
            p.highest_comp,
            p.former,
            p.comp_org,
            p.comp_related,
            p.comp_other,
        ]
        rows.append([_cell(v) for v in vals])
    return rows


def extract_batch(zip_path: Path, out_dir: Path, source_year: int) -> tuple[str, int, int]:
    stem = zip_path.stem
    fpath, ppath = out_dir / f"{stem}.filing.tsv", out_dir / f"{stem}.person.tsv"
    if fpath.exists() and fpath.stat().st_mtime > zip_path.stat().st_mtime:
        return stem, -1, 0
    errors: list[str] = []
    n = 0
    tmp_f, tmp_p = fpath.with_suffix(".part"), ppath.with_suffix(".part")
    try:
        with (
            open(tmp_f, "w", newline="", encoding="utf-8") as fh,
            open(tmp_p, "w", newline="", encoding="utf-8") as ph,
        ):
            for f in iter_zip(zip_path, on_error=lambda oid, e: errors.append(f"{oid}\t{e}")):
                fh.write("\t".join(filing_row(f, source_year)) + "\n")
                ph.writelines("\t".join(r) + "\n" for r in person_rows(f))
                n += 1
    except zipfile.BadZipFile:
        # Still downloading, or damaged: leave no output so the next run retries it.
        tmp_f.unlink(missing_ok=True)
        tmp_p.unlink(missing_ok=True)
        return stem, -2, 1
    os.replace(tmp_f, fpath)
    os.replace(tmp_p, ppath)
    (out_dir / f"{stem}.errors.txt").write_text("\n".join(errors), encoding="utf-8")
    return stem, n, len(errors)


def extract_all(data_dir: Path, work_dir: Path, years, jobs: int | None = None) -> list:
    work_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (z, work_dir, y)
        for y in years
        for z in sorted((data_dir / "xml" / str(y)).glob(f"{y}_TEOS_XML_*.zip"))
    ]
    jobs = jobs or max(1, (os.cpu_count() or 2) - 1)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(extract_batch, *t) for t in tasks]
        return [f.result() for f in futures]
