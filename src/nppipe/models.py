"""
src/nppipe/models.py
Project : Non-Profit Spending Reports
Date    : 2026-10-26
Purpose : Records the renderer works with: an organization's latest return
          with its size rank, the people listed on it, and the roles one
          person holds across organizations.
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

from dataclasses import dataclass

FORM_NAMES = {"990": "Form 990", "990EZ": "Form 990-EZ", "990PF": "Form 990-PF"}

# First letter of the NTEE code: the IRS's broad category of the organization.
NTEE_MAJOR = {
    "A": "Arts, culture and humanities",
    "B": "Education",
    "C": "Environment",
    "D": "Animal related",
    "E": "Health care",
    "F": "Mental health and crisis intervention",
    "G": "Voluntary health associations and medical disciplines",
    "H": "Medical research",
    "I": "Crime and legal related",
    "J": "Employment",
    "K": "Food, agriculture and nutrition",
    "L": "Housing and shelter",
    "M": "Public safety and disaster relief",
    "N": "Recreation and sports",
    "O": "Youth development",
    "P": "Human services",
    "Q": "International and foreign affairs",
    "R": "Civil rights and advocacy",
    "S": "Community improvement",
    "T": "Philanthropy and grantmaking",
    "U": "Science and technology",
    "V": "Social science",
    "W": "Public and societal benefit",
    "X": "Religion related",
    "Y": "Mutual and membership benefit",
    "Z": "Unknown",
}


@dataclass(frozen=True)
class Org:
    ein: str
    name: str
    city: str | None
    state: str | None
    form: str
    tax_year: int | None
    tax_period_end: str | None
    object_id: str
    revenue: int | None
    expenses: int | None
    assets: int | None
    program_expenses: int | None
    salaries: int | None
    comp_and_benefits: int | None
    employees: int | None
    website: str | None
    mission: str | None
    ntee_cd: str | None
    subsection: str | None
    rank: int
    measure: int | None
    has_page: bool = True
    top10_comp: int | None = None

    @property
    def form_name(self) -> str:
        return FORM_NAMES.get(self.form, self.form)

    @property
    def category(self) -> str | None:
        return NTEE_MAJOR.get((self.ntee_cd or " ")[0].upper())

    @property
    def ein_display(self) -> str:
        return f"{self.ein[:2]}-{self.ein[2:]}"

    @property
    def top10_share(self) -> float | None:
        """Top 10 listed people's pay as a share of the salary base."""
        if not self.salaries or self.top10_comp is None:
            return None
        return self.top10_comp / self.salaries

    @property
    def avg_salary(self) -> float | None:
        if not self.salaries or not self.employees:
            return None
        return self.salaries / self.employees


@dataclass(frozen=True)
class Role:
    org: Org
    name: str
    key: str | None
    title: str | None
    hours: float | None
    board: bool
    officer: bool
    key_employee: bool
    highest_comp: bool
    former: bool
    comp_org: int
    comp_related: int
    comp_other: int
    pay_rank: int

    @property
    def total_comp(self) -> int:
        return self.comp_org + self.comp_related + self.comp_other

    @property
    def kinds(self) -> str:
        out = []
        if self.board:
            out.append("Board")
        if self.officer:
            out.append("Officer")
        if self.key_employee:
            out.append("Key employee")
        if self.highest_comp:
            out.append("Highly paid employee")
        if self.former:
            out.append("Former")
        return ", ".join(out)
