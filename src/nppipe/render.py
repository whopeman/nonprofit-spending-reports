"""
src/nppipe/render.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Write the static site: home page (search box and top list),
          one page per organization and per listed person, A-Z browse
          pages, the search index, CSS, script and .htaccess.
          All links are relative so the site works under any folder
          (it is served from https://hopemanhorde.com/nonprofit-spending/).
Usage   : site = Site(out_dir=Path("site"), generated="2026-10-26", top_n=100)
          site.build(orgs, roles)                     # everything in memory
          or: common_pages(); home(); org_page(); person_page(); finish()
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

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


def person_slug(key: str) -> str:
    """Readable and unique: the key's slug plus a short hash of the exact key."""
    digest = hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:6]
    return slugify(key, digest)


def person_path(key: str) -> str:
    slug = person_slug(key)
    return f"person/{slug[:2]}/{slug}.html"


def hours(h) -> str:
    return "" if h is None else f"{h:g}"


def sentence(text: str | None) -> str:
    """Filers often type in all capitals; soften that, but keep mixed case as filed."""
    if not text:
        return ""
    return text[:1].upper() + text[1:].lower() if text.isupper() else text


def browse_letter(name: str) -> str:
    c = (name or "#")[:1].upper()
    return c.lower() if c.isalpha() else "0"


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
            pct=pct,
            person=display_name,
            orgname=nice_org_name,
        )
        self.env.globals.update(
            csp=CSP,
            version=__version__,
            generated=generated,
            repo_url=REPO_URL,
            org_slug=org_slug,
            person_path=person_path,
            phase2=self.phase2,
            phase3=self.phase3,
            top_n=top_n,
            rank_label=RANK_LABELS.get(rank_by, rank_by),
        )
        self._orgs_index: list[list] = []
        self._people_index: dict[str, list[list]] = defaultdict(list)
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

    def org_page(self, org: Org, roles: list[Role], person_pages: set[str] | None = None):
        """person_pages: keys that have a page (None means every key does)."""

        def linked(r: Role) -> bool:
            return r.key is not None and (person_pages is None or r.key in person_pages)

        top10 = sorted(roles, key=lambda r: (-r.total_comp, r.pay_rank))[:10]
        top10 = [r for r in top10 if r.total_comp > 0]
        board = [r for r in roles if r.board]
        others = [r for r in roles if not r.board and r not in top10]
        self._write(
            f"org/{org_slug(org)}.html",
            "org.html.j2",
            org=org,
            top10=top10,
            board=board,
            others=others,
            linked=linked,
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

    def person_page(self, key: str, roles: list[Role]) -> None:
        roles = sorted(roles, key=lambda r: (not r.org.has_page, r.org.rank))
        name = display_name(roles[0].name)
        self._write(person_path(key), "person.html.j2", key=key, name=name, roles=roles)
        orgs = len({r.org.ein for r in roles})
        entry = [name, orgs, person_path(key)]
        for letter in {w[0].lower() for w in key.split() if w[:1].isalpha()}:
            self._people_index[letter].append(entry)

    def finish(self) -> None:
        search = self.out / "search"
        search.mkdir(parents=True, exist_ok=True)
        (search / "orgs.json").write_text(
            json.dumps(sorted(self._orgs_index, key=lambda o: o[3]), separators=(",", ":")),
            encoding="utf-8",
        )
        for letter, entries in self._people_index.items():
            (search / f"people-{letter}.json").write_text(
                json.dumps(sorted(entries), separators=(",", ":")), encoding="utf-8"
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
        by_key: dict[str, list[Role]] = defaultdict(list)
        for r in roles:
            by_org[r.org.ein].append(r)
            if r.key:
                by_key[r.key].append(r)
        keys = {k for k, rs in by_key.items() if any(r.org.has_page for r in rs)}
        for o in paged:
            self.org_page(o, by_org[o.ein], keys)
        for k in sorted(keys):
            self.person_page(k, by_key[k])
        self.finish()
