"""
tests/test_format.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Money, percentage and slug helpers.
Change log:
  2026-10-26  0.1.0  Initial tests.
  2026-10-28  0.1.0  compact_usd at unit boundaries and below zero (torch).
"""

from nppipe.format import compact_usd, pct, slugify, usd


def test_usd():
    assert usd(1234567.5) == "$1,234,568"
    assert usd(-5) == "-$5"
    assert usd(None) == "not reported"


def test_compact_usd():
    assert compact_usd(2_450_000_000) == "$2.45B"
    assert compact_usd(12_300_000) == "$12.3M"
    assert compact_usd(950_000) == "$950K"
    assert compact_usd(None) == "not reported"


def test_compact_usd_rounds_up_to_next_unit():
    # .3g alone gave "$1e+03M" for these
    assert compact_usd(999_999_999) == "$1B"
    assert compact_usd(999_950) == "$1M"
    assert compact_usd(999_600_000_000) == "$1T"
    assert compact_usd(999_400) == "$999K"
    assert compact_usd(100_000_000) == "$100M"
    assert compact_usd(999) == "$999"


def test_compact_usd_negative():
    assert compact_usd(-2_450_000) == "-$2.45M"
    assert compact_usd(-5) == "-$5"


def test_pct():
    assert pct(1, 3) == "33.3%"
    assert pct(5, 0) == "0.0%"
    assert pct(5, None) == "0.0%"


def test_slugify():
    assert slugify("Carnegie Institute", "250965280") == "carnegie-institute-250965280"
    assert slugify("José & Co.", None) == "jose-co"
    assert len(slugify("x" * 200, "123")) <= 80
