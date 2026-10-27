"""
tests/test_render.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : The demo site renders, every internal link resolves, names are
          escaped, and pages carry the Content-Security-Policy.
Change log:
  2026-10-26  0.1.0  Initial tests.
"""

import json
import re
from html.parser import HTMLParser

import pytest

from nppipe.cli import demo_data
from nppipe.render import Site, person_slug


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
    assert len(list((site / "person").rglob("*.html"))) >= 4


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
    assert checked > 20


def test_home_lists_top_n_by_rank(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    top = html[html.index("<table") : html.index("</table>")]
    assert top.count("<tr>") == 3  # header + top_n rows
    assert top.index("Example Museums") < top.index("Sample Hospital")


def test_org_page_shows_board_top10_and_share(site):
    page = next((site / "org").glob("example-museums*.html")).read_text(encoding="utf-8")
    assert "Board members" in page
    assert "Top 10 paid" in page
    assert "$100,000,000" in page  # salary base
    assert "1.5%" in page  # top 10 share of the salary base
    assert person_slug("JANE EXAMPLE") in page


def test_person_page_lists_every_org(site):
    page = next((site / "person").rglob(f"{person_slug('SAM SAMPLE')}.html"))
    html = page.read_text(encoding="utf-8")
    assert "Example Museums" in html
    assert "Sample Family Foundation" in html
    assert "same name" in html  # matching caveat


def test_names_are_escaped(site):
    for page in site.rglob("*.html"):
        assert "<script>alert" not in page.read_text(encoding="utf-8")


def test_csp_on_every_page(site):
    for page in site.rglob("*.html"):
        assert 'http-equiv="Content-Security-Policy"' in page.read_text(encoding="utf-8")


def test_search_index(site):
    orgs = json.loads((site / "search" / "orgs.json").read_text(encoding="utf-8"))
    assert {o[0] for o in orgs} >= {"Example Museums of Springfield"}
    shard = json.loads((site / "search" / "people-s.json").read_text(encoding="utf-8"))
    assert any(p[0] == "Sam Sample" for p in shard)
    assert (site / "js" / "search.js").exists()


def test_person_slug_is_stable_and_safe():
    assert person_slug("JOHN SMITH") == person_slug("JOHN SMITH")
    assert person_slug("ANNE-MARIE ONEIL") != person_slug("ANNE MARIE-ONEIL")
    assert re.fullmatch(r"[a-z0-9-]+", person_slug("JOHN SMITH"))


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
