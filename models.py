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

class Policy:
    """Funding rules. Values are private and can only change through update()."""

    FIELDS = ("max_request_amount", "minimum_lead_days", "food_per_person_limit",
              "max_prize_amount", "equipment_quote_threshold", "ineligible_categories")
    # Optional so policy files from Part 1 still load (all rules on).
    OPTIONAL_FIELDS = ("disabled_rules",)

    MONEY_FIELDS = ("max_request_amount", "food_per_person_limit",
                    "max_prize_amount", "equipment_quote_threshold")

    def __init__(self, max_request_amount, minimum_lead_days, food_per_person_limit,
                 max_prize_amount, equipment_quote_threshold, ineligible_categories,
                 disabled_rules=None):
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
    def max_request_amount(self):
        return self._max_request_amount

    @property
    def minimum_lead_days(self):
        return self._minimum_lead_days

    @property
    def food_per_person_limit(self):
        return self._food_per_person_limit

    @property
    def max_prize_amount(self):
        return self._max_prize_amount

    @property
    def equipment_quote_threshold(self):
        return self._equipment_quote_threshold

    @property
    def ineligible_categories(self):
        return list(self._ineligible_categories)

    @property
    def disabled_rules(self):
        return list(self._disabled_rules)

    def is_rule_enabled(self, rule_id):
        return rule_id not in self._disabled_rules

    def update(self, changes):
        """Change policy values. Nothing changes if any value is invalid."""
        unknown = [field for field in changes if field not in self.FIELDS + self.OPTIONAL_FIELDS]
        if unknown:
            raise PolicyError(f"Unknown policy field: {unknown[0]}")

        values = self.to_dict()
        values.update(changes)
        self._apply(self._validate(values))

    def to_dict(self):
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
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise PolicyError("policy.json must contain an object.")

        for field in cls.FIELDS:
            if field not in data:
                raise PolicyError(f"Policy is missing: {field}")

        return cls(*(data[field] for field in cls.FIELDS), data.get("disabled_rules", []))

    def _apply(self, values):
        self._max_request_amount = values["max_request_amount"]
        self._minimum_lead_days = values["minimum_lead_days"]
        self._food_per_person_limit = values["food_per_person_limit"]
        self._max_prize_amount = values["max_prize_amount"]
        self._equipment_quote_threshold = values["equipment_quote_threshold"]
        self._ineligible_categories = list(values["ineligible_categories"])
        self._disabled_rules = list(values["disabled_rules"])

    @classmethod
    def _validate(cls, values):
        """Check every value and return a cleaned copy."""
        cleaned = {}

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
