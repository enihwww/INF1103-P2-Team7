from __future__ import annotations

from .check import Check
from .constants import JsonDict


class Assessment:
    """Result of applying the business rules. It owns (composes) its Check objects."""

    READY = "READY_FOR_REVIEW"
    REVISION = "REVISION_REQUIRED"
    MANUAL = "MANUAL_REVIEW"

    def __init__(self, funding_year: int | None, annual_budget: float, used_budget_before: float,
                 remaining_budget_before: float, total_requested: float, lead_days: int) -> None:
        self._funding_year = funding_year
        self._annual_budget = annual_budget
        self._used_budget_before = used_budget_before
        self._remaining_budget_before = remaining_budget_before
        self._total_requested = total_requested
        self._lead_days = lead_days
        self._checks: list[Check] = []
        self._issues: list[str] = []
        self._status: str | None = None
        self._estimated_eligible_amount = 0.0
        self._budget_to_commit = 0.0
        self._remaining_budget_after = remaining_budget_before

    def add_check(self, result: str, message: str) -> None:
        self._checks.append(Check(result, message))

    def add_issue(self, issue: str) -> None:
        self._issues.append(issue)

    def has_result(self, result: str) -> bool:
        """Return True if any check has this result."""
        for check in self._checks:
            if check.result == result:
                return True
        return False

    def decide_status(self) -> str:
        if self.has_result(Check.REVIEW):
            return self.MANUAL
        if self.has_result(Check.FAIL):
            return self.REVISION
        return self.READY

    def finalise(self, eligible_amount: float) -> None:
        """Set the status and the amount to take from the annual budget."""
        self._estimated_eligible_amount = eligible_amount
        self._status = self.decide_status()

        # Only take money from the budget if the request is ready.
        if self._status == self.READY:
            self._budget_to_commit = eligible_amount
        else:
            self._budget_to_commit = 0.0

        self._remaining_budget_after = round(
            max(0, self._remaining_budget_before - self._budget_to_commit), 2)

    @property
    def status(self) -> str | None:
        return self._status

    @property
    def funding_year(self) -> int | None:
        return self._funding_year

    @property
    def annual_budget(self) -> float:
        return self._annual_budget

    @property
    def used_budget_before(self) -> float:
        return self._used_budget_before

    @property
    def remaining_budget_before(self) -> float:
        return self._remaining_budget_before

    @property
    def total_requested(self) -> float:
        return self._total_requested

    @property
    def estimated_eligible_amount(self) -> float:
        return self._estimated_eligible_amount

    @property
    def budget_to_commit(self) -> float:
        return self._budget_to_commit

    @property
    def remaining_budget_after(self) -> float:
        return self._remaining_budget_after

    @property
    def lead_days(self) -> int:
        return self._lead_days

    @property
    def checks(self) -> list[Check]:
        return list(self._checks)

    @property
    def issues(self) -> list[str]:
        return list(self._issues)

    def to_dict(self) -> JsonDict:
        # Same key order as the Phase 1 assessment dictionary.
        return {
            "status": self._status,
            "funding_year": self._funding_year,
            "annual_budget": self._annual_budget,
            "used_budget_before": self._used_budget_before,
            "remaining_budget_before": self._remaining_budget_before,
            "total_requested": self._total_requested,
            "estimated_eligible_amount": self._estimated_eligible_amount,
            "budget_to_commit": self._budget_to_commit,
            "remaining_budget_after": self._remaining_budget_after,
            "lead_days": self._lead_days,
            "checks": [check.to_dict() for check in self._checks],
            "issues": list(self._issues)
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "Assessment":
        assessment = cls(data.get("funding_year"), data.get("annual_budget", 0.0),
                         data.get("used_budget_before", 0.0),
                         data.get("remaining_budget_before", 0.0),
                         data.get("total_requested", 0.0), data.get("lead_days", 0))

        for check in data.get("checks", []):
            assessment.add_check(check.get("result", ""), check.get("message", ""))
        for issue in data.get("issues", []):
            assessment.add_issue(issue)

        assessment._status = data.get("status")
        assessment._estimated_eligible_amount = data.get("estimated_eligible_amount", 0.0)
        assessment._budget_to_commit = data.get("budget_to_commit", 0.0)
        assessment._remaining_budget_after = data.get("remaining_budget_after", 0.0)
        return assessment
