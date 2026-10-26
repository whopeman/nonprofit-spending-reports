"""
src/nppipe/parse990.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Parse IRS Form 990 series e-file XML (TEOS bulk downloads) into
          Filing records: the filer, money totals, and the officers,
          directors, trustees, key and highest paid employees listed.
          Forms 990, 990-EZ and 990-PF are read; 990-T and others are skipped.
          XML is parsed with defusedxml (no DTDs or entities: OWASP XXE).
Usage   : parse_return(xml_bytes, object_id) -> Filing | None
          for f in iter_zip(Path("2025_TEOS_XML_01A.zip")): ...
Change log:
  2026-10-26  0.1.0  Initial version.
  2026-10-26  0.1.0  Read Deflate64 batches (some 2025-2026 zips) via inflate64.
"""

from __future__ import annotations

import re
import struct
import zipfile
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree.ElementTree import Element, ParseError

import inflate64
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

from nppipe.names import is_placeholder, person_key

NS = "{http://www.irs.gov/efile}"
FORMS = ("990", "990EZ", "990PF")
DEFLATE64 = 9  # zip compression method id
MAX_MEMBER_BYTES = 64 * 1024 * 1024  # the largest real returns are a few MB
_BOARD = re.compile(r"DIRECTOR|TRUSTEE|BOARD|CHAIR|GOVERNOR|MEMBER|REGENT")
_NOT_BOARD = re.compile(r"(EXECUTIVE|MANAGING|ASSOCIATE|ASSISTANT|PROGRAM|FINANCE|MEDICAL)\s+DIR")
_OFFICER = re.compile(
    r"PRES|CEO|CFO|COO|TREAS|SECRETARY|EXECUTIVE|VICE|OFFICER|CHAIR|\bVP\b|MANAGER|ADMIN"
)


@dataclass
class Person:
    name: str
    key: str | None  # None for businesses (institutional trustees)
    title: str | None
    hours: float | None
    board: bool
    officer: bool
    key_employee: bool = False
    highest_comp: bool = False
    former: bool = False
    comp_org: int = 0
    comp_related: int = 0
    comp_other: int = 0

    @property
    def total_comp(self) -> int:
        return self.comp_org + self.comp_related + self.comp_other


@dataclass
class Filing:
    object_id: str
    ein: str
    name: str
    city: str | None
    state: str | None
    form: str
    tax_year: int | None
    tax_period_end: str | None
    amended: bool
    revenue: int | None
    expenses: int | None
    assets: int | None
    program_expenses: int | None
    salaries: int | None
    comp_and_benefits: int | None
    employees: int | None
    website: str | None
    mission: str | None
    people: list[Person] = field(default_factory=list)


def _path(p: str) -> str:
    return "/".join(NS + part for part in p.split("/"))


def _text(el: Element | None, p: str) -> str | None:
    if el is None:
        return None
    found = el.find(_path(p))
    if found is None or found.text is None:
        return None
    t = re.sub(r"\s+", " ", found.text).strip()
    return t or None


def _int(el: Element | None, p: str) -> int | None:
    t = _text(el, p)
    if t is None:
        return None
    try:
        return round(float(t))
    except ValueError:
        return None


def _float(el: Element | None, p: str) -> float | None:
    t = _text(el, p)
    try:
        return float(t) if t is not None else None
    except ValueError:
        return None


def _flag(el: Element, p: str) -> bool:
    return (_text(el, p) or "").upper() in {"X", "TRUE", "1"}


def _sum(*vals: int | None) -> int | None:
    present = [v for v in vals if v is not None]
    return sum(present) if present else None


def _website(raw: str | None) -> str | None:
    if raw is None or is_placeholder(raw) or "." not in raw:
        return None
    return raw


def _part_vii(form: Element) -> list[Person]:
    out = []
    for g in form.findall(_path("Form990PartVIISectionAGrp")):
        person = _text(g, "PersonNm")
        business = " ".join(
            filter(
                None,
                (
                    _text(g, "BusinessName/BusinessNameLine1Txt"),
                    _text(g, "BusinessName/BusinessNameLine2Txt"),
                ),
            )
        )
        name = person or business
        if not name or is_placeholder(name):
            continue
        out.append(
            Person(
                name=name,
                key=person_key(person) if person else None,
                title=_text(g, "TitleTxt"),
                hours=_float(g, "AverageHoursPerWeekRt"),
                board=_flag(g, "IndividualTrusteeOrDirectorInd")
                or _flag(g, "InstitutionalTrusteeInd"),
                officer=_flag(g, "OfficerInd"),
                key_employee=_flag(g, "KeyEmployeeInd"),
                highest_comp=_flag(g, "HighestCompensatedEmployeeInd"),
                former=_flag(g, "FormerOfcrDirectorTrusteeInd"),
                comp_org=_int(g, "ReportableCompFromOrgAmt") or 0,
                comp_related=_int(g, "ReportableCompFromRltdOrgAmt") or 0,
                comp_other=_int(g, "OtherCompensationAmt") or 0,
            )
        )
    return out


def _listed(groups: list[Element]) -> list[Person]:
    """990-EZ Part IV and 990-PF Part VIII: one combined list, roles from titles."""
    out = []
    for g in groups:
        name = _text(g, "PersonNm") or _text(g, "BusinessName/BusinessNameLine1Txt")
        if not name or is_placeholder(name):
            continue
        title = (_text(g, "TitleTxt") or "").upper()
        board = bool(_BOARD.search(title)) and not _NOT_BOARD.search(title)
        out.append(
            Person(
                name=name,
                key=person_key(_text(g, "PersonNm")) if _text(g, "PersonNm") else None,
                title=_text(g, "TitleTxt"),
                hours=_float(g, "AverageHrsPerWkDevotedToPosRt"),
                board=board,
                officer=bool(_OFFICER.search(title)) and not (board and "CHAIR" not in title),
                comp_org=_int(g, "CompensationAmt") or 0,
                comp_other=(_int(g, "EmployeeBenefitProgramAmt") or 0)
                + (_int(g, "ExpenseAccountOtherAllwncAmt") or 0),
            )
        )
    return out


def parse_return(data: bytes, object_id: str) -> Filing | None:
    """Parse one return. Returns None for forms other than 990, 990-EZ, 990-PF."""
    try:
        root = fromstring(data.lstrip(b"\xef\xbb\xbf"), forbid_dtd=True)
    except DefusedXmlException as e:
        raise ValueError(f"unsafe XML in {object_id}: {type(e).__name__}") from e
    except ParseError as e:
        raise ValueError(f"bad XML in {object_id}: {e}") from e

    head = root.find(_path("ReturnHeader"))
    form_type = (_text(head, "ReturnTypeCd") or "").upper()
    if form_type not in FORMS:
        return None
    body = root.find(_path(f"ReturnData/IRS{form_type}"))
    if body is None:
        return None

    name = " ".join(
        filter(
            None,
            (
                _text(head, "Filer/BusinessName/BusinessNameLine1Txt"),
                _text(head, "Filer/BusinessName/BusinessNameLine2Txt"),
            ),
        )
    )
    city = _text(head, "Filer/USAddress/CityNm") or _text(head, "Filer/ForeignAddress/CityNm")
    state = _text(head, "Filer/USAddress/StateAbbreviationCd")
    tax_year = _int(head, "TaxYr")

    if form_type == "990":
        revenue = _int(body, "CYTotalRevenueAmt")
        expenses = _int(body, "CYTotalExpensesAmt")
        assets = _int(body, "TotalAssetsEOYAmt")
        program = _int(body, "TotalProgramServiceExpensesAmt")
        salaries = _sum(
            _int(body, "CompCurrentOfcrDirectorsGrp/TotalAmt"),
            _int(body, "CompDisqualPersonsGrp/TotalAmt"),
            _int(body, "OtherSalariesAndWagesGrp/TotalAmt"),
        )
        comp_benefits = _int(body, "CYSalariesCompEmpBnftPaidAmt")
        employees = _int(body, "TotalEmployeeCnt")
        mission = _text(body, "ActivityOrMissionDesc") or _text(body, "MissionDesc")
        people = _part_vii(body)
    elif form_type == "990EZ":
        revenue = _int(body, "TotalRevenueAmt")
        expenses = _int(body, "TotalExpensesAmt")
        assets = _int(body, "Form990TotalAssetsGrp/EOYAmt")
        program = _int(body, "TotalProgramServiceExpensesAmt")
        salaries = comp_benefits = _int(body, "SalariesOtherCompEmplBnftAmt")
        employees = None
        mission = _text(body, "PrimaryExemptPurposeTxt")
        people = _listed(body.findall(_path("OfficerDirectorTrusteeEmplGrp")))
    else:  # 990PF
        a = body.find(_path("AnalysisOfRevenueAndExpenses"))
        revenue = _int(a, "TotalRevAndExpnssAmt")
        expenses = _int(a, "TotalExpensesRevAndExpnssAmt")
        assets = _int(body, "Form990PFBalanceSheetsGrp/TotalAssetsEOYAmt")
        program = None
        salaries = _sum(
            _int(a, "CompOfficersDirTrstRevAndExpnssAmt"),
            _int(a, "OthEmplSalariesWagesRevAndExpnssAmt"),
        )
        comp_benefits = _sum(salaries, _int(a, "PensionEmplBnftRevAndExpnssAmt"))
        employees = None
        mission = None
        people = _listed(
            body.findall(_path("OfficerDirTrstKeyEmplInfoGrp/OfficerDirTrstKeyEmplGrp"))
        )

    website = _text(body, "WebsiteAddressTxt") or _text(
        body, "StatementsRegardingActyGrp/WebsiteAddressTxt"
    )
    return Filing(
        object_id=object_id,
        ein=_text(head, "Filer/EIN") or "",
        name=name,
        city=city,
        state=state,
        form=form_type,
        tax_year=tax_year,
        tax_period_end=_text(head, "TaxPeriodEndDt"),
        amended=_flag(body, "AmendedReturnInd"),
        revenue=revenue,
        expenses=expenses,
        assets=assets,
        program_expenses=program,
        salaries=salaries,
        comp_and_benefits=comp_benefits,
        employees=employees,
        website=_website(website),
        mission=mission,
        people=people,
    )


def object_id_of(member: str) -> str:
    return Path(member).name.removesuffix(".xml").removesuffix("_public")


def read_member(z: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """Read one member. Some IRS batches use Deflate64 (method 9), which the
    standard library cannot read, so those are inflated with inflate64.
    Oversized members are refused (zip bomb guard)."""
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"{info.filename} is {info.file_size:,} bytes, over the limit")
    if info.compress_type != DEFLATE64:
        return z.read(info)
    fp = z.fp
    if fp is None:
        raise ValueError("zip file is closed")
    fp.seek(info.header_offset)
    header = fp.read(30)
    if header[:4] != b"PK\x03\x04":
        raise ValueError(f"bad local header for {info.filename}")
    name_len, extra_len = struct.unpack("<HH", header[26:30])
    fp.seek(info.header_offset + 30 + name_len + extra_len)
    data = inflate64.Inflater().inflate(fp.read(info.compress_size))
    if len(data) != info.file_size or zlib.crc32(data) != info.CRC:
        raise ValueError(f"Deflate64 member {info.filename} failed its size or CRC check")
    return data


def iter_zip(
    path: Path,
    wanted: set[str] | None = None,
    on_error: Callable[[str, Exception], None] | None = None,
) -> Iterator[Filing]:
    """Parse every return in one TEOS batch zip, optionally only `wanted` object ids."""
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if not info.filename.endswith(".xml"):
                continue
            oid = object_id_of(info.filename)
            if wanted is not None and oid not in wanted:
                continue
            try:
                f = parse_return(read_member(z, info), oid)
            except ValueError as e:
                if on_error:
                    on_error(oid, e)
                continue
            if f is not None:
                yield f
