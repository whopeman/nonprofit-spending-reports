"""
src/nppipe/render.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Write the static site: home page (search box and top list),
          one page per organization (its leadership and top 10 paid),
          A-Z browse pages, the search index, CSS, script and .htaccess.
          All links are relative so the site works under any folder
          (it is served from https://hopemanhorde.com/nonprofit-spending/).
Usage   : site = Site(out_dir=Path("site"), generated="2026-10-26", top_n=100)
          site.build(orgs, roles)                     # everything in memory
          or: common_pages(); home(); org_page(); finish()
Change log:
  2026-10-26  0.1.0  Initial version.
  2026-10-28  0.1.0  Org pages list only leadership and the top 10 paid; no
                     person pages or people search.
  2026-10-28  0.1.0  A-Z: skip leading punctuation ('IOLANI SCHOOL is on I) and
                     file accented letters under the plain letter (they were
                     on no page) (torch).
"""

from __future__ import annotations

import json
import shutil
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import escape

from nppipe import __version__
from nppipe.format import compact_usd, pct, slugify, usd
from nppipe.models import Org, Role
from nppipe.names import display_name

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
REPO_URL = "https://github.com/whopeman/nonprofit-spending-reports"
RANK_LABELS = {"revenue": "total revenue", "expenses": "total expenses", "assets": "total assets"}
LETTERS = [*"abcdefghijklmnopqrstuvwxyz", "0"]

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'"
)


def org_slug(org: Org) -> str:
    return slugify(org.name, org.ein)


def leadership(roles: list[Role]) -> list[Role]:
    """Current officers, key employees, then directors and trustees; best paid
    first within each group. Former officers are left out (they can still be
    in the top 10 paid)."""
    leaders = [r for r in roles if not r.former and (r.officer or r.key_employee or r.board)]
    return sorted(
        leaders,
        key=lambda r: (0 if r.officer else 1 if r.key_employee else 2, -r.total_comp, r.pay_rank),
    )


def top_paid(roles: list[Role], n: int = 10) -> list[Role]:
    top = sorted(roles, key=lambda r: (-r.total_comp, r.pay_rank))[:n]
    return [r for r in top if r.total_comp > 0]


def hours(h) -> str:
    return "" if h is None else f"{h:g}"


def short_title(text: str, limit: int = 54) -> str:
    """Shorten text so its HTML-escaped form fits in limit characters (the site
    name follows it in <title>, and validators count &amp; in full)."""
    if len(escape(text)) <= limit:
        return text
    while text and len(escape(text)) > limit - 1:
        text = text[:-1]
    return text.rstrip(" ,&-") + "…"


def sentence(text: str | None) -> str:
    """Filers often type in all capitals; soften that, but keep mixed case as filed."""
    if not text:
        return ""
    return text[:1].upper() + text[1:].lower() if text.isupper() else text


def browse_letter(name: str) -> str:
    """The A-Z page a name is listed on: "École" on e, "'Iolani" on i, and
    digits and anything else on 0."""
    first = (name or "").lstrip(" '\"`.,-(ʻ‘’“")[:1]
    c = unicodedata.normalize("NFKD", first)[:1].lower()
    return c if c in LETTERS else "0"


def nice_org_name(name: str) -> str:
    small = {"OF", "THE", "AND", "FOR", "IN", "AT", "ON", "TO", "A", "AN"}
    words = display_name(name).split(" ")
    return " ".join(w.lower() if i and w.upper() in small else w for i, w in enumerate(words))


class Site:
    def __init__(
        self,
        out_dir: Path,
        generated: str,
        top_n: int = 100,
        rank_by: str = "revenue",
        page_rule: str = "",
        phase2_spending: bool = False,
        phase3_violations: bool = False,
    ):
        self.out = Path(out_dir)
        self.generated = generated
        self.top_n = top_n
        self.phase2 = phase2_spending
        self.phase3 = phase3_violations
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES),
            autoescape=select_autoescape(["html", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters.update(
            usd=usd,
            cusd=compact_usd,
            hrs=hours,
            sentence=sentence,
            short_title=short_title,
            pct=pct,
            person=display_name,
            orgname=nice_org_name,
        )
        self.env.globals.update(
            csp=CSP,
            version=__version__,
            page_rule=page_rule,
            generated=generated,
            repo_url=REPO_URL,
            org_slug=org_slug,
            phase2=self.phase2,
            phase3=self.phase3,
            top_n=top_n,
            rank_label=RANK_LABELS.get(rank_by, rank_by),
        )
        self._orgs_index: list[list] = []
        self._browse: dict[str, list[Org]] = defaultdict(list)

    # -- helpers ----------------------------------------------------------------
    def _write(self, rel: str, template: str, **ctx) -> None:
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        root = "../" * rel.count("/")
        html = self.env.get_template(template).render(root=root, **ctx)
        path.write_text(html, encoding="utf-8")

    # -- pages ------------------------------------------------------------------
    def common_pages(self) -> None:
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / "css").mkdir(parents=True)
        (self.out / "js").mkdir()
        shutil.copy(STATIC / "css" / "site.css", self.out / "css" / "site.css")
        shutil.copy(STATIC / "js" / "search.js", self.out / "js" / "search.js")
        shutil.copy(STATIC / "htaccess", self.out / ".htaccess")
        self._write("about.html", "about.html.j2")

    def home(self, top: list[Org], org_count: int) -> None:
        self._write("index.html", "home.html.j2", top=top[: self.top_n], org_count=org_count)

    def org_page(self, org: Org, roles: list[Role]) -> None:
        self._write(
            f"org/{org_slug(org)}.html",
            "org.html.j2",
            org=org,
            leaders=leadership(roles),
            top10=top_paid(roles),
        )
        self._orgs_index.append(
            [
                nice_org_name(org.name),
                org.city or "",
                org.state or "",
                org.rank,
                f"org/{org_slug(org)}.html",
            ]
        )
        self._browse[browse_letter(nice_org_name(org.name))].append(org)

    def finish(self) -> None:
        search = self.out / "search"
        search.mkdir(parents=True, exist_ok=True)
        (search / "orgs.json").write_text(
            json.dumps(sorted(self._orgs_index, key=lambda o: o[3]), separators=(",", ":")),
            encoding="utf-8",
        )
        for letter in LETTERS:
            orgs = sorted(self._browse.get(letter, []), key=lambda o: nice_org_name(o.name).upper())
            self._write(
                f"browse/{letter}.html", "browse.html.j2", letter=letter, orgs=orgs, letters=LETTERS
            )

    # -- all in memory (demo and tests) ----------------------------------------
    def build(self, orgs: Iterable[Org], roles: Iterable[Role]) -> None:
        orgs = sorted(orgs, key=lambda o: o.rank)
        roles = list(roles)
        self.common_pages()
        paged = [o for o in orgs if o.has_page]
        self.home(paged, len(paged))
        by_org: dict[str, list[Role]] = defaultdict(list)
        for r in roles:
            by_org[r.org.ein].append(r)
        for o in paged:
            self.org_page(o, by_org[o.ein])
        self.finish()
