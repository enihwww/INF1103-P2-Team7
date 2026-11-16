from __future__ import annotations

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
