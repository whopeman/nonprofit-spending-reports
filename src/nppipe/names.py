"""
src/nppipe/names.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Person names on Form 990 are free text with no ID number, so people
          are matched across organizations by a normalized key: first and
          last name, upper case, without titles, suffixes, initials, middle
          names or notes in brackets. Different people can share a key; every
          person page says so.
Usage   : person_key("Dr. John Q. Smith, Jr.") -> "JOHN SMITH"
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import re
import unicodedata

TITLES = {"MR", "MRS", "MS", "MISS", "DR", "HON", "REV", "FR", "PROF", "SISTER", "BROTHER"}
SUFFIXES = {
    "JR",
    "SR",
    "II",
    "III",
    "IV",
    "V",
    "MD",
    "PHD",
    "DO",
    "JD",
    "CPA",
    "ESQ",
    "RN",
    "MBA",
    "DDS",
    "DMD",
    "EDD",
    "CFA",
    "CFP",
    "PE",
    "DVM",
    "MSW",
    "LCSW",
    "FACHE",
    "FACP",
    "FACS",
}
_PLACEHOLDER = re.compile(
    r"^(SEE\b|NONE\b|N/?A$|NOT APPLICABLE|VARIOUS|ATTACHED|STATEMENT\b|SCHEDULE\b|VACANT)"
)
_NOTES = re.compile(r"\(.*?\)|\[.*?\]")
# Banks and companies filed as institutional trustees sometimes appear as PersonNm.
_BUSINESS = re.compile(
    r"\b(BANK|BANCORP|TRUST|TRUSTCO|CO|COMPANY|CORP|CORPORATION|INC|LLC|LLP|LP|LTD|PLLC|"
    r"FOUNDATION|ASSOCIATION|FUND|PARTNERS|HOLDINGS|UNIVERSITY|COLLEGE|CHURCH|SERVICES|"
    r"ADVISORS|CAPITAL|INVESTMENTS|MELLON|PNC|TRUIST|FIDUCIARY|NA)\b"
)
# Job titles that some filers run into the name field ("JANE DOE VP FINANCE").
_ROLE_WORDS = {
    "VP",
    "SVP",
    "EVP",
    "AVP",
    "CEO",
    "CFO",
    "COO",
    "CIO",
    "CTO",
    "CMO",
    "PRESIDENT",
    "DIRECTOR",
    "EXECUTIVE",
    "TREASURER",
    "SECRETARY",
    "CHAIR",
    "CHAIRMAN",
    "CHAIRPERSON",
    "CHAIRWOMAN",
    "TRUSTEE",
    "MANAGER",
    "OFFICER",
    "COUNSEL",
    "VICE",
    "BOARD",
    "MEMBER",
    "FORMER",
    "INTERIM",
    "ASSOCIATE",
    "ASSISTANT",
    "SENIOR",
    "CHIEF",
}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def is_placeholder(raw: str | None) -> bool:
    t = _fold(raw or "").strip().upper()
    return not t or bool(_PLACEHOLDER.search(t))


def _tokens(raw: str) -> list[str]:
    t = _NOTES.sub(" ", _fold(raw).upper())
    if t.count(",") == 1:
        last, rest = (s.strip() for s in t.split(","))
        rest_words = [w.replace(".", "") for w in rest.split()]
        # "SMITH, JOHN Q" is last-first; "JOHN SMITH, CPA" is a suffix.
        if rest_words and not all(w in SUFFIXES for w in rest_words):
            t = f"{rest} {last}"
    words = []
    for w in re.split(r"[\s,]+", t):
        w = w.replace("'", "").replace(".", "").strip("-")
        if not w or w in TITLES or w in SUFFIXES:
            continue
        words.append(w)
    return words


def is_business(raw: str | None) -> bool:
    t = _fold(raw or "").upper().replace(".", "")
    words = re.split(r"[\s,]+", t.strip())
    # "NA" alone after one word is also a surname (JOHN NA), so it needs a bank word too.
    if words[-1:] == ["NA"] and len(words) == 2 and words[0] not in {"PNC", "BNY"}:
        return False
    return bool(_BUSINESS.search(t))


def person_key(raw: str | None) -> str | None:
    if is_placeholder(raw) or is_business(raw):
        return None
    words = [w for w in _tokens(raw or "") if re.fullmatch(r"[A-Z][A-Z-]*", w)]
    for i, w in enumerate(words):
        if i >= 2 and w in _ROLE_WORDS:
            words = words[:i]
            break
    if not words:
        return None
    named = [w for w in words if len(w) > 1] or words
    if len(named) == 1:
        return named[0]
    return f"{named[0]} {named[-1]}"


def _title_word(w: str) -> str:
    if w.upper() in {"II", "III", "IV"}:
        return w.upper()
    out = "-".join(p[:1].upper() + p[1:].lower() for p in w.split("-"))
    out = re.sub(r"^(Mc|O')([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    return out


def display_name(raw: str | None) -> str:
    """Readable form of the name as filed, without notes in brackets."""
    t = re.sub(r"\s+", " ", _NOTES.sub(" ", raw or "")).strip(" ,")
    if t.isupper() or t.islower():
        t = " ".join(_title_word(w) for w in t.split(" "))
    return t
