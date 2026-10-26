"""
tests/test_extract.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Batch zips become PostgreSQL COPY files with safe text cells.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

import zipfile
from pathlib import Path

from nppipe.extract import FILING_COLS, PERSON_COLS, _cell, extract_batch

FIX = Path(__file__).parent / "fixtures"


def test_cell_escapes_copy_specials():
    assert _cell(None) == r"\N"
    assert _cell(True) == "t"
    assert _cell("a\tb\nc\\d") == "a b c/d"
    assert _cell(12) == "12"


def test_extract_batch_writes_rows(tmp_path):
    z = tmp_path / "2025_TEOS_XML_01A.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("x/202500000000000001_public.xml", (FIX / "f990.xml").read_bytes())
        zf.writestr("x/202500000000000002_public.xml", (FIX / "f990pf.xml").read_bytes())
    stem, n, errors = extract_batch(z, tmp_path, 2025)
    assert (stem, n, errors) == ("2025_TEOS_XML_01A", 2, 0)
    filings = (tmp_path / f"{stem}.filing.tsv").read_text(encoding="utf-8").splitlines()
    people = (tmp_path / f"{stem}.person.tsv").read_text(encoding="utf-8").splitlines()
    assert len(filings) == 2
    assert all(len(r.split("\t")) == len(FILING_COLS) + 1 for r in filings)
    assert filings[0].split("\t")[-1] == "2025"
    assert len(people) == 5 + 1
    assert all(len(r.split("\t")) == len(PERSON_COLS) for r in people)
    # A second run skips a batch that is already done.
    assert extract_batch(z, tmp_path, 2025)[1] == -1


def test_extract_batch_reports_incomplete_zip(tmp_path):
    z = tmp_path / "2025_TEOS_XML_02A.zip"
    z.write_bytes(b"PK\x03\x04 half a download")
    assert extract_batch(z, tmp_path, 2025) == ("2025_TEOS_XML_02A", -2, 1)
    assert not list(tmp_path.glob("*.tsv"))
