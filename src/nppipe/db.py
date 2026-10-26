"""
src/nppipe/db.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Render the site from the "site" schema built by sql/20_site.sql.
          Roles are streamed with server-side cursors, grouped by
          organization and then by person, so memory stays modest.
Usage   : build_from_db(site, dsn="dbname=nonprofit")
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from itertools import groupby

import psycopg
from psycopg import sql

from nppipe.models import Org, Role
from nppipe.render import Site

ORG_COLS = (
    "ein, name, city, state, form, tax_year, tax_period_end::text, object_id, revenue, expenses, "
    "assets, program_expenses, salaries, comp_and_benefits, employees, website, mission, "
    "ntee_cd, subsection, rank, measure, coalesce(has_page, false), top10_comp"
)
ROLE_COLS = (
    "r.ein, r.name, r.key, r.title, r.hours::float, r.board, r.officer, r.key_employee, "
    "r.highest_comp, r.former, r.comp_org, r.comp_related, r.comp_other, r.pay_rank"
)


def _orgs(conn, schema: str) -> dict[str, Org]:
    """Organizations with pages, plus any other that lists a person with a page."""
    q = sql.SQL(
        """SELECT {cols} FROM {s}.org o
           WHERE o.has_page OR EXISTS (
             SELECT 1 FROM {s}.role r JOIN {s}.person p USING (key) WHERE r.ein = o.ein)"""
    ).format(cols=sql.SQL(ORG_COLS), s=sql.Identifier(schema))
    with conn.cursor(name="orgs") as cur:
        cur.itersize = 50_000
        cur.execute(q)
        return {r[0]: Org(*r) for r in cur}


def _role(r, orgs: dict[str, Org]) -> Role | None:
    org = orgs.get(r[0])
    if org is None:
        return None
    return Role(org, *r[1:])


def _iter(conn, name: str, q: sql.Composed) -> Iterator[tuple]:
    with conn.cursor(name=name) as cur:
        cur.itersize = 50_000
        cur.execute(q)
        yield from cur


def build_from_db(site: Site, dsn: str | None = None, schema: str = "site") -> dict:
    dsn = dsn or os.environ.get("NP_DSN", "dbname=nonprofit")
    counts = {"orgs": 0, "people": 0}
    s = sql.Identifier(schema)
    site.common_pages()
    with psycopg.connect(dsn) as conn:
        orgs = _orgs(conn, schema)
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT key FROM {}.person").format(s))
            person_keys = {r[0] for r in cur}

        paged = sorted((o for o in orgs.values() if o.has_page), key=lambda o: o.rank)
        site.home(paged, len(paged))

        q = sql.SQL(
            "SELECT {cols} FROM {s}.role r JOIN {s}.org o USING (ein) "
            "WHERE o.has_page ORDER BY r.ein, r.pay_rank"
        ).format(cols=sql.SQL(ROLE_COLS), s=s)
        for ein, rows in groupby(_iter(conn, "org_roles", q), key=lambda r: r[0]):
            roles = [x for x in (_role(r, orgs) for r in rows) if x]
            site.org_page(orgs[ein], roles, person_keys)
            counts["orgs"] += 1
        # Organizations with a page but nobody listed still get a page.
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT DISTINCT ein FROM {}.role").format(s))
            listed = {r[0] for r in cur}
        for o in paged:
            if o.ein not in listed:
                site.org_page(o, [], person_keys)
                counts["orgs"] += 1

        q = sql.SQL(
            "SELECT r.key, {cols} FROM {s}.role r JOIN {s}.person p USING (key) ORDER BY r.key"
        ).format(cols=sql.SQL(ROLE_COLS), s=s)
        for key, rows in groupby(_iter(conn, "person_roles", q), key=lambda r: r[0]):
            roles = [x for x in (_role(r[1:], orgs) for r in rows) if x]
            if roles:
                site.person_page(key, roles)
                counts["people"] += 1
    site.finish()
    return counts
