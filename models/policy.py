from __future__ import annotations

import math

from .constants import JsonDict, LOCKED_RULES, RULE_NAMES, VALID_CATEGORIES
from .policy_error import PolicyError


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
