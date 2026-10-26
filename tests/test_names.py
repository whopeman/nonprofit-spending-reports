"""
tests/test_names.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Person names from Form 990 Part VII normalize to one matching key,
          and placeholder entries ("SEE SCHEDULE") are rejected.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

import pytest

from nppipe.names import display_name, is_placeholder, person_key


@pytest.mark.parametrize(
    "raw",
    [
        "JOHN Q SMITH",
        "John Smith",
        "DR. JOHN SMITH",
        "JOHN SMITH JR",
        "John Smith, Ph.D.",
        "  JOHN   SMITH  ",
        "JOHN SMITH (THROUGH 6/22)",
        "JOHN SMITH, CPA",
    ],
)
def test_variants_share_a_key(raw):
    assert person_key(raw) == "JOHN SMITH"


def test_last_comma_first_is_reordered():
    assert person_key("SMITH, JOHN Q") == "JOHN SMITH"


def test_full_middle_name_is_dropped():
    assert person_key("MARY ELIZABETH JONES") == "MARY JONES"


def test_hyphenated_and_apostrophe_names_kept():
    assert person_key("Anne-Marie O'Neil") == "ANNE-MARIE ONEIL"


def test_accents_folded():
    assert person_key("José Núñez") == "JOSE NUNEZ"


def test_single_word_is_kept():
    assert person_key("MADONNA") == "MADONNA"


@pytest.mark.parametrize(
    "raw",
    ["SEE SCHEDULE ATTACHED", "See Statement 7", "NONE", "N/A", "", "   ", "SEE ATTACHED LIST"],
)
def test_placeholders(raw):
    assert is_placeholder(raw)
    assert person_key(raw) is None


def test_display_name_title_cases_and_strips_notes():
    assert display_name("JOHN Q SMITH (THROUGH 6/22)") == "John Q Smith"
    assert display_name("ANNE-MARIE O'NEIL") == "Anne-Marie O'Neil"
    assert display_name("MARY MCDONALD III") == "Mary McDonald III"
