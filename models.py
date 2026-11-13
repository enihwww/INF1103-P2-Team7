from __future__ import annotations

import math
from datetime import date
from typing import Any

# A JSON object loaded from or saved to a file.
JsonDict = dict[str, Any]

# Annual, used and remaining budget of one club for one year.
BudgetInfo = dict[str, float]


# Categories and event types the AI is allowed to return.
# Kept here so the AI manager and the Policy class share one definition.
VALID_EVENT_TYPES = {"competition", "workshop", "social",
    "training", "community_service", "other", "unknown"}

VALID_CATEGORIES = {"food", "prize", "reusable_equipment",
    "venue", "transport", "marketing",
    "decoration", "other", "unknown"}


# Business rules an admin can switch on or off (id -> label shown to users).
RULE_NAMES = {
    "request_limit": "Single request limit",
    "remaining_budget": "Remaining annual budget",
    "lead_time": "Minimum lead time",
    "unclear_information": "Unclear AI information",
    "equipment_quote": "Equipment supplier quote",
    "ineligible_category": "Ineligible categories",
    "food_limit": "Food per-person limit",
    "prize_limit": "Competition prize limit",
}

# This rule sends unclear or failed AI results to a human, so it cannot be turned off.
LOCKED_RULES = {"unclear_information"}


class PolicyError(ValueError):
    """Raised when a policy value is missing or invalid."""


class Expense:
    """One expense item inside a funding request."""

    def __init__(self, expense_id: str, description: str, amount: float, quote_available: bool) -> None:
        self._expense_id = expense_id
        self._description = description
        self._amount = round(float(amount), 2)
        self._quote_available = bool(quote_available)

    @property
    def expense_id(self) -> str:
        return self._expense_id

    @property
    def description(self) -> str:
        return self._description

    @property
    def amount(self) -> float:
        return self._amount

    @property
    def quote_available(self) -> bool:
        return self._quote_available

    def to_dict(self) -> JsonDict:
        return {
            "expense_id": self._expense_id,
            "description": self._description,
            "amount": self._amount,
            "quote_available": self._quote_available
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "Expense":
        return cls(data.get("expense_id", ""), data.get("description", ""),
                   data.get("amount", 0), data.get("quote_available", False))


class FundingRequest:
    """A club funding request. It owns (composes) its Expense objects."""

    def __init__(self, request_id: str, club_name: str, event_title: str, event_description: str,
                 event_date: str, submission_date: str, expected_participants: int,
                 funding_year: int | None = None) -> None:
        self._request_id = request_id
        self._club_name = club_name
        self._event_title = event_title
        self._event_description = event_description
        self._event_date = event_date
        self._submission_date = submission_date
        self._expected_participants = expected_participants
        self._expenses: list[Expense] = []

        # Use the event year as the funding year (same rule as Phase 1).
        if funding_year is None and event_date:
            funding_year = int(event_date[:4])
        self._funding_year = funding_year

    @property
    def request_id(self) -> str:
        return self._request_id

    @property
    def club_name(self) -> str:
        return self._club_name

    @property
    def event_title(self) -> str:
        return self._event_title

    @property
    def event_description(self) -> str:
        return self._event_description

    @property
    def event_date(self) -> str:
        return self._event_date

    @property
    def submission_date(self) -> str:
        return self._submission_date

    @property
    def expected_participants(self) -> int:
        return self._expected_participants

    @property
    def funding_year(self) -> int | None:
        return self._funding_year

    @property
    def expenses(self) -> list[Expense]:
        # Return a copy so callers cannot change the list directly.
        return list(self._expenses)

    def add_expense(self, description: str, amount: float, quote_available: bool) -> None:
        """Create the next expense (E1, E2...) inside this request."""
        expense_id = f"E{len(self._expenses) + 1}"
        self._expenses.append(Expense(expense_id, description, amount, quote_available))

    def total_amount(self) -> float:
        """Add all expense amounts."""
        total = 0.0
        for expense in self._expenses:
            total += expense.amount
        return round(total, 2)

    def lead_days(self) -> int:
        """Return the number of days between submission and event."""
        submitted = date.fromisoformat(self._submission_date)
        event = date.fromisoformat(self._event_date)
        return (event - submitted).days

    def to_dict(self) -> JsonDict:
        # Same key order as the Phase 1 records in requests.json.
        return {
            "request_id": self._request_id,
            "club_name": self._club_name,
            "event_title": self._event_title,
            "event_description": self._event_description,
            "event_date": self._event_date,
            "submission_date": self._submission_date,
            "expected_participants": self._expected_participants,
            "expenses": [expense.to_dict() for expense in self._expenses],
            "funding_year": self._funding_year
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "FundingRequest":
        request = cls(data.get("request_id", ""), data.get("club_name", ""),
                      data.get("event_title", ""), data.get("event_description", ""),
                      data.get("event_date", ""), data.get("submission_date", ""),
                      data.get("expected_participants", 0), data.get("funding_year"))

        for item in data.get("expenses", []):
            request._expenses.append(Expense.from_dict(item))
        return request


class Policy:
    """Funding rules. Values are private and can only change through update()."""

    FIELDS = ("max_request_amount", "minimum_lead_days", "food_per_person_limit",
              "max_prize_amount", "equipment_quote_threshold", "ineligible_categories")
    # Optional so policy files from Part 1 still load (all rules on).
    OPTIONAL_FIELDS = ("disabled_rules",)

    MONEY_FIELDS = ("max_request_amount", "food_per_person_limit",
                    "max_prize_amount", "equipment_quote_threshold")

    def __init__(self, max_request_amount: float, minimum_lead_days: int, food_per_person_limit: float,
                 max_prize_amount: float, equipment_quote_threshold: float, ineligible_categories: list[str],
                 disabled_rules: list[str] | None = None) -> None:
        values = self._validate({
            "max_request_amount": max_request_amount,
            "minimum_lead_days": minimum_lead_days,
            "food_per_person_limit": food_per_person_limit,
            "max_prize_amount": max_prize_amount,
            "equipment_quote_threshold": equipment_quote_threshold,
            "ineligible_categories": ineligible_categories,
            "disabled_rules": disabled_rules if disabled_rules is not None else []
        })
        self._apply(values)

    @property
    def max_request_amount(self) -> float:
        return self._max_request_amount

    @property
    def minimum_lead_days(self) -> int:
        return self._minimum_lead_days

    @property
    def food_per_person_limit(self) -> float:
        return self._food_per_person_limit

    @property
    def max_prize_amount(self) -> float:
        return self._max_prize_amount

    @property
    def equipment_quote_threshold(self) -> float:
        return self._equipment_quote_threshold

    @property
    def ineligible_categories(self) -> list[str]:
        return list(self._ineligible_categories)

    @property
    def disabled_rules(self) -> list[str]:
        return list(self._disabled_rules)

    def is_rule_enabled(self, rule_id: str) -> bool:
        return rule_id not in self._disabled_rules

    def update(self, changes: JsonDict) -> None:
        """Change policy values. Nothing changes if any value is invalid."""
        unknown = [field for field in changes if field not in self.FIELDS + self.OPTIONAL_FIELDS]
        if unknown:
            raise PolicyError(f"Unknown policy field: {unknown[0]}")

        values = self.to_dict()
        values.update(changes)
        self._apply(self._validate(values))

    def to_dict(self) -> JsonDict:
        return {
            "max_request_amount": self._max_request_amount,
            "minimum_lead_days": self._minimum_lead_days,
            "food_per_person_limit": self._food_per_person_limit,
            "max_prize_amount": self._max_prize_amount,
            "equipment_quote_threshold": self._equipment_quote_threshold,
            "ineligible_categories": list(self._ineligible_categories),
            "disabled_rules": list(self._disabled_rules)
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "Policy":
        if not isinstance(data, dict):
            raise PolicyError("policy.json must contain an object.")

        for field in cls.FIELDS:
            if field not in data:
                raise PolicyError(f"Policy is missing: {field}")

        return cls(data["max_request_amount"], data["minimum_lead_days"], data["food_per_person_limit"],
                   data["max_prize_amount"], data["equipment_quote_threshold"], data["ineligible_categories"],
                   data.get("disabled_rules", []))

    def _apply(self, values: JsonDict) -> None:
        self._max_request_amount = values["max_request_amount"]
        self._minimum_lead_days = values["minimum_lead_days"]
        self._food_per_person_limit = values["food_per_person_limit"]
        self._max_prize_amount = values["max_prize_amount"]
        self._equipment_quote_threshold = values["equipment_quote_threshold"]
        self._ineligible_categories = list(values["ineligible_categories"])
        self._disabled_rules = list(values["disabled_rules"])

    @classmethod
    def _validate(cls, values: JsonDict) -> JsonDict:
        """Check every value and return a cleaned copy."""
        cleaned: JsonDict = {}

        for field in cls.MONEY_FIELDS:
            value = values[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(value) or value < 0:
                raise PolicyError(f"{field} must be a number of 0 or more.")
            cleaned[field] = round(float(value), 2)

        lead_days = values["minimum_lead_days"]
        if isinstance(lead_days, bool) or not isinstance(lead_days, int) or lead_days < 0:
            raise PolicyError("minimum_lead_days must be a whole number of 0 or more.")
        cleaned["minimum_lead_days"] = lead_days

        categories = values["ineligible_categories"]
        if not isinstance(categories, list):
            raise PolicyError("ineligible_categories must be a list.")

        for category in categories:
            if category not in VALID_CATEGORIES:
                raise PolicyError(f"Unknown expense category: {category}")
        cleaned["ineligible_categories"] = list(dict.fromkeys(categories))

        disabled = values["disabled_rules"]
        if not isinstance(disabled, list):
            raise PolicyError("disabled_rules must be a list.")

        for rule_id in disabled:
            if rule_id not in RULE_NAMES:
                raise PolicyError(f"Unknown rule: {rule_id}")
            if rule_id in LOCKED_RULES:
                raise PolicyError(f"{RULE_NAMES[rule_id]} cannot be turned off.")
        cleaned["disabled_rules"] = list(dict.fromkeys(disabled))

        return cleaned


class Check:
    """One PASS, FAIL or REVIEW message."""

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    SKIPPED = "SKIPPED"  # rule turned off by an admin; does not affect the status

    def __init__(self, result: str, message: str) -> None:
        self._result = result
        self._message = message

    @property
    def result(self) -> str:
        return self._result

    @property
    def message(self) -> str:
        return self._message

    def to_dict(self) -> dict[str, str]:
        return {"result": self._result, "message": self._message}


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


class FundingRecord:
    """A saved request together with its AI result and assessment."""

    PROCESSED = "PROCESSED"
    AI_FAILED = "AI_FAILED"

    def __init__(self, request: FundingRequest, ai_result: JsonDict | None, assessment: Assessment | None,
                 processing_status: str, processing_error: str | None = None,
                 budget_committed: bool = False, budget_amount: float = 0.0) -> None:
        self._request = request
        self._ai_result = ai_result
        self._assessment = assessment
        self._processing_status = processing_status
        self._processing_error = processing_error
        self._budget_committed = budget_committed
        self._budget_amount = budget_amount

    @property
    def request(self) -> FundingRequest:
        return self._request

    @property
    def request_id(self) -> str:
        return self._request.request_id

    @property
    def club_name(self) -> str:
        return self._request.club_name

    @property
    def funding_year(self) -> int | None:
        return self._request.funding_year

    @property
    def ai_result(self) -> JsonDict | None:
        return self._ai_result

    @property
    def assessment(self) -> Assessment | None:
        return self._assessment

    @property
    def processing_status(self) -> str:
        return self._processing_status

    @property
    def processing_error(self) -> str | None:
        return self._processing_error

    @property
    def budget_committed(self) -> bool:
        return self._budget_committed

    @property
    def budget_amount(self) -> float:
        return self._budget_amount

    def to_dict(self) -> JsonDict:
        record = self._request.to_dict()
        record["ai_result"] = self._ai_result
        record["assessment"] = self._assessment.to_dict() if self._assessment else None
        record["processing_status"] = self._processing_status
        record["processing_error"] = self._processing_error
        record["budget_committed"] = self._budget_committed
        record["budget_amount"] = self._budget_amount
        return record

    @classmethod
    def from_dict(cls, data: JsonDict) -> "FundingRecord":
        assessment_data = data.get("assessment")
        assessment = Assessment.from_dict(assessment_data) if assessment_data else None

        return cls(FundingRequest.from_dict(data), data.get("ai_result"), assessment,
                   data.get("processing_status", ""), data.get("processing_error"),
                   data.get("budget_committed", False), data.get("budget_amount", 0.0))
