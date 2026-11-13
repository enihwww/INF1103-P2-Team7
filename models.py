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
