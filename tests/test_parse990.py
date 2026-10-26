"""
tests/test_parse990.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : The IRS e-file XML parser pulls the filer, the money totals and
          the people listed on Forms 990, 990-EZ and 990-PF.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

import io
import struct
import zipfile
import zlib
from pathlib import Path

import pytest

from nppipe.parse990 import iter_zip, parse_return

FIX = Path(__file__).parent / "fixtures"


def load(name: str):
    return parse_return((FIX / name).read_bytes(), object_id="202500000000000001")


def test_990_filer_and_totals():
    f = load("f990.xml")
    assert f.object_id == "202500000000000001"
    assert f.ein == "990000001"
    assert f.name == "EXAMPLE MUSEUMS OF SPRINGFIELD"
    assert (f.city, f.state) == ("SPRINGFIELD", "PA")
    assert f.form == "990"
    assert f.tax_year == 2023
    assert f.tax_period_end == "2024-06-30"
    assert f.amended is True
    assert f.revenue == 200_000_000
    assert f.expenses == 190_000_000
    assert f.assets == 900_000_000
    assert f.program_expenses == 150_000_000
    # Salary base = Part IX lines 5 + 6 + 7 (officers, disqualified persons, everyone else).
    assert f.salaries == 100_000_000
    assert f.comp_and_benefits == 120_000_000
    assert f.employees == 4000
    assert f.website == "WWW.EXAMPLE.ORG"
    assert f.mission == "TO RUN EXAMPLE MUSEUMS"


def test_990_people():
    people = {p.name: p for p in load("f990.xml").people}
    jane = people["JANE Q EXAMPLE"]
    assert jane.key == "JANE EXAMPLE"
    assert jane.title == "PRESIDENT & CEO"
    assert jane.hours == 50.0
    assert jane.officer and not jane.board
    assert jane.comp_org == 900_000
    assert jane.comp_related == 50_000
    assert jane.comp_other == 60_000
    assert jane.total_comp == 1_010_000

    sam = people["SAM SAMPLE"]
    assert sam.board and sam.officer
    assert sam.total_comp == 0

    pat = people["PAT PLACEHOLDER"]
    assert pat.highest_comp and not pat.board

    assert people["OLD FORMER"].former
    assert people["OLD FORMER"].comp_related == 0


def test_990_institutional_trustee_is_kept_but_not_a_person():
    trust = [p for p in load("f990.xml").people if p.name == "FIRST EXAMPLE TRUST CO"]
    assert len(trust) == 1
    assert trust[0].board
    assert trust[0].key is None  # businesses do not get person pages


def test_990ez():
    f = load("f990ez.xml")
    assert f.form == "990EZ"
    assert (f.revenue, f.expenses, f.assets) == (111_640, 110_548, 182_020)
    assert f.salaries == 38_466
    assert f.employees is None
    assert f.website is None  # "N/A" is not a website
    assert f.mission == "PROVISION OF SUPPORT TO SAILING"
    casey, jane = f.people
    assert casey.total_comp == 31_500
    assert casey.officer and not casey.board
    assert jane.board and not jane.officer


def test_990pf_skips_placeholder_people():
    f = load("f990pf.xml")
    assert f.form == "990PF"
    assert (f.revenue, f.expenses, f.assets) == (118_066, 70_413, 1_214_045)
    assert f.salaries == 25_000
    assert f.comp_and_benefits == 26_000
    assert [p.name for p in f.people] == ["SAM SAMPLE"]
    assert f.people[0].board and f.people[0].total_comp == 20_000


def test_990t_is_skipped():
    assert load("f990t.xml") is None


def test_rejects_entity_expansion():
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
        b'<Return xmlns="http://www.irs.gov/efile"><r>&b;</r></Return>'
    )
    with pytest.raises(ValueError, match="unsafe"):
        parse_return(bomb, object_id="x")


def test_iter_zip_reads_every_member(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("batch/202500000000000001_public.xml", (FIX / "f990.xml").read_bytes())
        z.writestr("batch/202500000000000002_public.xml", (FIX / "f990t.xml").read_bytes())
        z.writestr("batch/202500000000000003_public.xml", b"not xml")
    path = tmp_path / "b.zip"
    path.write_bytes(buf.getvalue())
    filings, errors = [], []
    for f in iter_zip(path, on_error=lambda oid, e: errors.append(oid)):
        filings.append(f)
    assert [f.object_id for f in filings] == ["202500000000000001"]
    assert errors == ["202500000000000003"]


def _deflate64_zip(tmp_path, member: str, payload: bytes, file_size: int | None = None):
    """A zip whose member is Deflate64-compressed (the standard library cannot write these)."""
    import inflate64

    d = inflate64.Deflater()
    packed = d.deflate(payload) + d.flush()
    path = tmp_path / "d64.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        z.writestr(member, packed)
    raw = bytearray(path.read_bytes())
    # Rewrite method (9), CRC and uncompressed size in the local and central headers.
    crc = zlib.crc32(payload)
    size = len(payload) if file_size is None else file_size
    for sig, method_at, crc_at, usize_at in (
        (b"PK\x03\x04", 8, 14, 22),
        (b"PK\x01\x02", 10, 16, 24),
    ):
        i = raw.index(sig)
        struct.pack_into("<H", raw, i + method_at, 9)
        struct.pack_into("<I", raw, i + crc_at, crc)
        struct.pack_into("<I", raw, i + usize_at, size)
    path.write_bytes(bytes(raw))
    return path


def test_reads_deflate64_members(tmp_path):
    xml = (FIX / "f990.xml").read_bytes()
    path = _deflate64_zip(tmp_path, "b/202500000000000001_public.xml", xml)
    assert [f.ein for f in iter_zip(path)] == ["990000001"]


def test_deflate64_size_mismatch_is_an_error(tmp_path):
    xml = (FIX / "f990.xml").read_bytes()
    path = _deflate64_zip(tmp_path, "b/202500000000000001_public.xml", xml, len(xml) + 5)
    errors = []
    assert list(iter_zip(path, on_error=lambda oid, e: errors.append(str(e)))) == []
    assert "CRC" in errors[0]
