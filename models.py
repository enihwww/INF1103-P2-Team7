import math
from datetime import date

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

    def __init__(self, expense_id, description, amount, quote_available):
        self._expense_id = expense_id
        self._description = description
        self._amount = round(float(amount), 2)
        self._quote_available = bool(quote_available)

    @property
    def expense_id(self):
        return self._expense_id

    @property
    def description(self):
        return self._description

    @property
    def amount(self):
        return self._amount

    @property
    def quote_available(self):
        return self._quote_available

    def to_dict(self):
        return {
            "expense_id": self._expense_id,
            "description": self._description,
            "amount": self._amount,
            "quote_available": self._quote_available
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data.get("expense_id", ""), data.get("description", ""),
                   data.get("amount", 0), data.get("quote_available", False))

class FundingRequest:
    """A club funding request. It owns (composes) its Expense objects."""

    def __init__(self, request_id, club_name, event_title, event_description,
                 event_date, submission_date, expected_participants, funding_year=None):
        self._request_id = request_id
        self._club_name = club_name
        self._event_title = event_title
        self._event_description = event_description
        self._event_date = event_date
        self._submission_date = submission_date
        self._expected_participants = expected_participants
        self._expenses = []

        # Use the event year as the funding year (same rule as Phase 1).
        if funding_year is None and event_date:
            funding_year = int(event_date[:4])
        self._funding_year = funding_year

    @property
    def request_id(self):
        return self._request_id

    @property
    def club_name(self):
        return self._club_name

    @property
    def event_title(self):
        return self._event_title

    @property
    def event_description(self):
        return self._event_description

    @property
    def event_date(self):
        return self._event_date

    @property
    def submission_date(self):
        return self._submission_date

    @property
    def expected_participants(self):
        return self._expected_participants

    @property
    def funding_year(self):
        return self._funding_year

    @property
    def expenses(self):
        # Return a copy so callers cannot change the list directly.
        return list(self._expenses)

    def add_expense(self, description, amount, quote_available):
        """Create the next expense (E1, E2...) inside this request."""
        expense_id = f"E{len(self._expenses) + 1}"
        self._expenses.append(Expense(expense_id, description, amount, quote_available))

    def total_amount(self):
        """Add all expense amounts."""
        total = 0
        for expense in self._expenses:
            total += expense.amount
        return round(total, 2)

    def lead_days(self):
        """Return the number of days between submission and event."""
        submitted = date.fromisoformat(self._submission_date)
        event = date.fromisoformat(self._event_date)
        return (event - submitted).days

    def to_dict(self):
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
    def from_dict(cls, data):
        request = cls(data.get("request_id", ""), data.get("club_name", ""),
                      data.get("event_title", ""), data.get("event_description", ""),
                      data.get("event_date", ""), data.get("submission_date", ""),
                      data.get("expected_participants", 0), data.get("funding_year"))

        for item in data.get("expenses", []):
            request._expenses.append(Expense.from_dict(item))
        return request
