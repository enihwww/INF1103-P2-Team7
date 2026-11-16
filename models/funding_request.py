from __future__ import annotations

from datetime import date

from .constants import JsonDict
from .expense import Expense


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
