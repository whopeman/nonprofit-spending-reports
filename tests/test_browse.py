"""
tests/test_browse.py
Project : Non-Profit Spending Reports
Date    : 2026-10-28
Purpose : Every organization name is filed under one of the A-Z pages.
Change log:
  2026-10-28  0.1.0  Initial tests (torch).
"""

import pytest

from nppipe.render import LETTERS, browse_letter


@pytest.mark.parametrize(
    ("name", "letter"),
    [
        ("Carnegie Institute", "c"),
        ("École Française", "e"),
        ("Ñandu Fund", "n"),
        ("'Iolani School", "i"),
        ("ʻIolani School", "i"),
        ('"Y" Camp', "y"),
        ("4-H Council", "0"),
        ("", "0"),
        ("ß Society", "0"),
        ("Ωmega Club", "0"),
    ],
)
def test_browse_letter(name, letter):
    assert browse_letter(name) == letter
    assert browse_letter(name) in LETTERS
