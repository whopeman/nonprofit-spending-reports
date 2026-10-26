"""
src/nppipe/flags.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Load feature flags from config/flags.toml, with NP_<NAME>
          environment variables taking precedence.
Usage   : flags = load_flags(Path("config/flags.toml"))
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "flags.toml"
RANK_BY = ("revenue", "expenses", "assets")
FIRST_XML_YEAR = 2019  # earliest TEOS XML processing year the IRS publishes


@dataclass(frozen=True)
class Flags:
    use_gpu: bool
    filing_years: tuple[int, ...]
    rank_by: str
    top_n: int
    org_page_min_usd: int
    page_by: str
    page_top_pct: float
    phase2_spending: bool
    phase3_violations: bool


def _bool(name: str, raw: str) -> bool:
    v = raw.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"NP_{name.upper()} must be true or false, got {raw!r}")


def _years(values) -> tuple[int, ...]:
    out = tuple(int(v) for v in values)
    for y in out:
        if y < FIRST_XML_YEAR:
            raise ValueError(f"filing year {y} must be {FIRST_XML_YEAR} or later")
    return out


def load_flags(path: Path = DEFAULT_PATH, env: Mapping[str, str] | None = None) -> Flags:
    env = os.environ if env is None else env
    with open(path, "rb") as fh:
        data = tomllib.load(fh)

    def get(name: str):
        key = f"NP_{name.upper()}"
        if key not in env:
            return data[name], False
        return env[key], True

    def boolean(name: str) -> bool:
        raw, from_env = get(name)
        return _bool(name, raw) if from_env else bool(raw)

    raw, from_env = get("filing_years")
    years = _years(raw.split(",") if from_env else raw)
    rank_by = str(get("rank_by")[0]).strip().lower()
    if rank_by not in RANK_BY:
        raise ValueError(f"rank_by must be one of {', '.join(RANK_BY)}, got {rank_by!r}")
    top_n = int(get("top_n")[0])
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    min_usd = int(get("org_page_min_usd")[0])
    if min_usd < 0:
        raise ValueError("org_page_min_usd must not be negative")
    page_by = str(get("page_by")[0]).strip().lower()
    if page_by not in RANK_BY:
        raise ValueError(f"page_by must be one of {', '.join(RANK_BY)}, got {page_by!r}")
    top_pct = float(get("page_top_pct")[0])
    if not 0 < top_pct <= 100:
        raise ValueError("page_top_pct must be above 0 and at most 100")

    return Flags(
        use_gpu=boolean("use_gpu"),
        filing_years=years,
        rank_by=rank_by,
        top_n=top_n,
        org_page_min_usd=min_usd,
        page_by=page_by,
        page_top_pct=top_pct,
        phase2_spending=boolean("phase2_spending"),
        phase3_violations=boolean("phase3_violations"),
    )
