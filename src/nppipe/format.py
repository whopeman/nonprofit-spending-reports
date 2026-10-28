"""
src/nppipe/format.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Display helpers: whole-dollar and compact money, percentages, and
          URL-safe slugs for page file names.
Change log:
  2026-10-26  0.1.0  Initial version (from Campaign Donations).
  2026-10-28  0.1.0  compact_usd: round before choosing the unit, so $999,999,999
                     shows as $1B, not $1e+03M (torch).
"""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

MAX_SLUG = 80
MISSING = "not reported"


def usd(amount) -> str:
    if amount is None:
        return MISSING
    d = Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    return f"{sign}${abs(int(d)):,}"


def compact_usd(amount) -> str:
    """$2.45B, $12.3M, $950K: for tables where whole dollars are too wide."""
    if amount is None:
        return MISSING
    a = float(f"{float(amount):.3g}")  # 3 significant figures, rounded once
    for div, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(a) >= div:
            return f"{'-' if a < 0 else ''}${abs(a) / div:g}{unit}"
    return usd(amount)


def pct(part, whole) -> str:
    if not whole:
        return "0.0%"
    return f"{float(part or 0) / float(whole) * 100:.1f}%"


def slugify(name: str | None, ident: str | None) -> str:
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    tail = re.sub(r"[^a-z0-9]+", "", (ident or "").lower())
    if not tail:
        return base[:MAX_SLUG].strip("-")
    room = MAX_SLUG - len(tail) - 1
    base = base[:room].strip("-")
    return f"{base}-{tail}" if base else tail
