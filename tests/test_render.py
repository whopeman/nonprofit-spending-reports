"""
tests/test_render.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : The demo site renders, every internal link resolves, names are
          escaped, and pages carry the Content-Security-Policy.
Change log:
  2026-10-26  0.1.0  Initial tests.
  2026-10-28  0.1.0  Leadership and top 10 only; no person pages.
"""

import json
import re
from html.parser import HTMLParser

import pytest

from nppipe.cli import demo_data
from nppipe.render import Site


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in {"href", "src"} and v:
                self.hrefs.append(v)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    s = Site(out_dir=out, generated="2026-10-26", top_n=2)
    s.build(*demo_data())
    return out


def test_pages_exist(site):
    assert (site / "index.html").exists()
    assert (site / "about.html").exists()
    assert (site / ".htaccess").exists()
    assert len(list((site / "org").glob("*.html"))) == 3
    assert not (site / "person").exists()


def test_internal_links_resolve(site):
    root = site.resolve()
    checked = 0
    for page in site.rglob("*.html"):
        p = Links()
        p.feed(page.read_text(encoding="utf-8"))
        for href in p.hrefs:
            if re.match(r"^(https?:|mailto:|#)", href):
                continue
            target = (page.parent / href.split("#")[0]).resolve()
            if not target.is_relative_to(root):
                continue  # the link up to hopemanhorde.com
            assert target.exists(), f"{page.name} links to missing {href}"
            checked += 1
    assert checked > 10


def test_home_lists_top_n_by_rank(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    top = html[html.index("<table") : html.index("</table>")]
    assert top.count("<tr>") == 3  # header + top_n rows
    assert top.index("Example Museums") < top.index("Sample Hospital")


def _section(page: str, heading_id: str) -> str:
    start = page.index(f'id="{heading_id}"')
    return page[start : page.index("</section>", start)]


def test_org_page_shows_leadership_top10_and_share(site):
    page = next((site / "org").glob("example-museums*.html")).read_text(encoding="utf-8")
    assert "Leadership" in page
    assert "Top 10 paid" in page
    assert "Board members" not in page
    assert "Other officers" not in page
    assert "$100,000,000" in page  # salary base
    assert "1.5%" in page  # top 10 share of the salary base
    assert "person/" not in page  # no person pages to link to


def test_leadership_lists_officers_and_board_with_pay(site):
    page = next((site / "org").glob("example-museums*.html")).read_text(encoding="utf-8")
    lead = _section(page, "lead-h")
    assert lead.index("Jane Q Example") < lead.index("Sam Sample")  # officers first, best paid
    assert "$1,010,000" in lead  # Jane's total pay
    assert "First Example Trust Co" in lead  # institutional trustee
    assert "None reported" in lead  # unpaid board members
    assert "Pat Placeholder" not in lead  # highly paid employee, not a leader
    assert "Old Former" not in lead  # former officer
    top = _section(page, "top-h")
    assert "Pat Placeholder" in top
    assert "Old Former" in top
    assert "Sam Sample" not in top  # unpaid


def test_names_are_escaped(site):
    for page in site.rglob("*.html"):
        assert "<script>alert" not in page.read_text(encoding="utf-8")


def test_csp_on_every_page(site):
    for page in site.rglob("*.html"):
        assert 'http-equiv="Content-Security-Policy"' in page.read_text(encoding="utf-8")


def test_search_index(site):
    orgs = json.loads((site / "search" / "orgs.json").read_text(encoding="utf-8"))
    assert {o[0] for o in orgs} >= {"Example Museums of Springfield"}
    assert not list((site / "search").glob("people-*.json"))
    assert (site / "js" / "search.js").exists()


def test_phase_flags_hide_unbuilt_sections(tmp_path):
    s = Site(out_dir=tmp_path, generated="2026-10-26", top_n=2)
    s.build(*demo_data())
    page = next((tmp_path / "org").glob("example-museums*.html")).read_text(encoding="utf-8")
    assert "Program spending" not in page
    s2 = Site(out_dir=tmp_path / "p2", generated="2026-10-26", top_n=2, phase2_spending=True)
    s2.build(*demo_data())
    page2 = next((tmp_path / "p2" / "org").glob("example-museums*.html")).read_text("utf-8")
    assert "Program spending" in page2


def test_page_titles_fit_70_characters(tmp_path):
    from dataclasses import replace

    orgs, roles = demo_data()
    long = replace(orgs[0], name="EXAMPLE & SONS' " * 15 + "MUSEUMS")
    roles = [replace(r, org=long) if r.org.ein == long.ein else r for r in roles]
    Site(out_dir=tmp_path, generated="2026-10-26", top_n=2).build([long, *orgs[1:]], roles)
    for page in tmp_path.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        title = html[html.index("<title>") + 7 : html.index("</title>")]
        # html-validate counts the source text, so entities such as &amp; count in full.
        assert len(title) <= 70, page.name
