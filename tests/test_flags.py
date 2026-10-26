"""
tests/test_flags.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Feature flags load from TOML and can be overridden by environment.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

import pytest

from nppipe.flags import DEFAULT_PATH, load_flags


@pytest.fixture
def flags_file(tmp_path):
    p = tmp_path / "flags.toml"
    p.write_text(
        'use_gpu = true\nfiling_years = [2024, 2025]\nrank_by = "revenue"\ntop_n = 100\n'
        "org_page_min_usd = 1000000\nphase2_spending = false\nphase3_violations = false\n",
        encoding="utf-8",
    )
    return p


def test_reads_values_from_file(flags_file):
    flags = load_flags(flags_file, env={})
    assert flags.use_gpu is True
    assert flags.filing_years == (2024, 2025)
    assert flags.rank_by == "revenue"
    assert flags.top_n == 100
    assert flags.org_page_min_usd == 1_000_000
    assert flags.phase2_spending is False
    assert flags.phase3_violations is False


def test_shipped_flags_file_loads():
    assert load_flags(DEFAULT_PATH, env={}).top_n > 0


def test_env_overrides(flags_file):
    flags = load_flags(
        flags_file,
        env={
            "NP_USE_GPU": "false",
            "NP_TOP_N": "250",
            "NP_FILING_YEARS": "2026",
            "NP_RANK_BY": "Assets",
            "NP_PHASE2_SPENDING": "yes",
        },
    )
    assert flags.use_gpu is False
    assert flags.top_n == 250
    assert flags.filing_years == (2026,)
    assert flags.rank_by == "assets"
    assert flags.phase2_spending is True


def test_rejects_bad_bool(flags_file):
    with pytest.raises(ValueError, match="NP_USE_GPU"):
        load_flags(flags_file, env={"NP_USE_GPU": "maybe"})


def test_rejects_unknown_rank(flags_file):
    with pytest.raises(ValueError, match="rank_by"):
        load_flags(flags_file, env={"NP_RANK_BY": "vibes"})


def test_rejects_bad_year(flags_file):
    with pytest.raises(ValueError, match="year"):
        load_flags(flags_file, env={"NP_FILING_YEARS": "2015"})


def test_rejects_non_positive_top_n(flags_file):
    with pytest.raises(ValueError, match="top_n"):
        load_flags(flags_file, env={"NP_TOP_N": "0"})
