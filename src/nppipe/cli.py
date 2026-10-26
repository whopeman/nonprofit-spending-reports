"""
src/nppipe/cli.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Command line entry point.
Usage   : nppipe extract [--data ~/np-data] [--work ~/np-data/work] [--jobs N]
          nppipe demo  [--out site]   render a small made-up data set (layout check)
          nppipe build [--out site]   render the site from the PostgreSQL database
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from nppipe.flags import load_flags
from nppipe.models import Org, Role


def _org(ein, name, city, state, form, rank, revenue, salaries, employees, top10, **kw) -> Org:
    return Org(
        ein=ein,
        name=name,
        city=city,
        state=state,
        form=form,
        tax_year=2024,
        tax_period_end="2024-12-31",
        object_id=f"2025{ein}0",
        revenue=revenue,
        expenses=kw.get("expenses", revenue),
        assets=kw.get("assets", revenue * 3),
        program_expenses=kw.get("program"),
        salaries=salaries,
        comp_and_benefits=kw.get("comp", salaries),
        employees=employees,
        website=None,
        mission=kw.get("mission"),
        ntee_cd=kw.get("ntee"),
        subsection="03",
        rank=rank,
        measure=revenue,
        has_page=kw.get("has_page", True),
        top10_comp=top10,
    )


def _role(
    org,
    seq,
    name,
    key,
    title,
    *,
    board=False,
    officer=False,
    hce=False,
    former=False,
    comp=0,
    related=0,
    other=0,
    hours=40.0,
) -> Role:
    return Role(
        org, name, key, title, hours, board, officer, False, hce, former, comp, related, other, seq
    )


def demo_data() -> tuple[list[Org], list[Role]]:
    """Clearly made-up records, for checking layout without the database."""
    museums = _org(
        "990000001",
        "EXAMPLE MUSEUMS OF SPRINGFIELD",
        "SPRINGFIELD",
        "PA",
        "990",
        1,
        200_000_000,
        100_000_000,
        4000,
        1_540_000,
        program=150_000_000,
        expenses=190_000_000,
        mission="TO RUN EXAMPLE MUSEUMS (DEMO)",
        ntee="A51",
    )
    hospital = _org(
        "990000004",
        "SAMPLE HOSPITAL INC",
        "ERIE",
        "PA",
        "990",
        2,
        150_000_000,
        60_000_000,
        900,
        2_000_000,
        ntee="E22",
    )
    fdn = _org(
        "990000003",
        "SAMPLE FAMILY FOUNDATION",
        "RICHMOND",
        "IN",
        "990PF",
        3,
        40_000_000,
        25_000,
        None,
        20_000,
        ntee="T20",
    )
    small = _org(
        "990000002",
        "DEMO SAILING CLUB INC",
        "ERIE",
        "PA",
        "990EZ",
        4,
        111_640,
        38_466,
        None,
        30_000,
        has_page=False,
    )
    roles = [
        _role(
            museums,
            1,
            "JANE Q EXAMPLE",
            "JANE EXAMPLE",
            "PRESIDENT & CEO",
            officer=True,
            comp=900_000,
            related=50_000,
            other=60_000,
            hours=50,
        ),
        _role(
            museums, 2, "SAM SAMPLE", "SAM SAMPLE", "BOARD CHAIR", board=True, officer=True, hours=2
        ),
        _role(
            museums,
            3,
            "PAT PLACEHOLDER",
            "PAT PLACEHOLDER",
            "CHIEF CURATOR",
            hce=True,
            comp=300_000,
            other=20_000,
        ),
        _role(
            museums, 4, "OLD FORMER", "OLD FORMER", "FORMER CFO", former=True, comp=210_000, hours=0
        ),
        _role(museums, 5, "FIRST EXAMPLE TRUST CO", None, "TRUSTEE", board=True, hours=1),
        _role(
            museums, 6, "ALEX DEMO", "ALEX DEMO", "<script>alert('x')</script>", board=True, hours=1
        ),
        _role(hospital, 1, "CHRIS SAMPLE", "CHRIS SAMPLE", "CEO", officer=True, comp=2_000_000),
        _role(hospital, 2, "Jane Example", "JANE EXAMPLE", "DIRECTOR", board=True, hours=1),
        _role(fdn, 1, "SAM SAMPLE", "SAM SAMPLE", "TRUSTEE", board=True, comp=20_000, hours=2),
        _role(small, 1, "SAM SAMPLE", "SAM SAMPLE", "PRESIDENT", officer=True, hours=5),
    ]
    return [museums, hospital, fdn, small], roles


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nppipe")
    ap.add_argument("command", choices=["extract", "demo", "build"])
    ap.add_argument("--out", type=Path, default=Path("site"))
    ap.add_argument("--data", type=Path, default=Path.home() / "np-data")
    ap.add_argument("--work", type=Path, default=None)
    ap.add_argument("--jobs", type=int, default=None)
    args = ap.parse_args(argv)
    flags = load_flags()

    if args.command == "extract":
        from nppipe.extract import extract_all

        work = args.work or args.data / "work"
        results = extract_all(args.data, work, flags.filing_years, args.jobs)
        done = [r for r in results if r[1] >= 0]
        bad = [r[0] for r in results if r[1] == -2]
        skipped = len(results) - len(done) - len(bad)
        print(
            f"{len(done)} batches parsed, {skipped} already done, "
            f"{sum(r[1] for r in done):,} returns, {sum(r[2] for r in done):,} bad returns"
        )
        if bad:
            print(f"unreadable zips (incomplete download?): {', '.join(bad)}")
        return 1 if bad else 0

    from nppipe.render import Site

    site = Site(
        out_dir=args.out,
        generated=dt.date.today().isoformat(),
        top_n=flags.top_n,
        rank_by=flags.rank_by,
        page_rule=(
            f"the top {flags.page_top_pct:g}% by total {flags.page_by} of organizations with "
            f"at least ${flags.org_page_min_usd:,} in total {flags.rank_by}, plus the top "
            f"{flags.top_n} list"
        ),
        phase2_spending=flags.phase2_spending,
        phase3_violations=flags.phase3_violations,
    )
    if args.command == "demo":
        site.build(*demo_data())
    else:
        from nppipe.db import build_from_db

        counts = build_from_db(site)
        print(f"{counts['orgs']:,} organization pages, {counts['people']:,} person pages")
    print(f"wrote site to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
