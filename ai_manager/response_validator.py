from __future__ import annotations

from typing import Any

from models import FundingRequest, VALID_CATEGORIES, VALID_EVENT_TYPES


class ResponseValidator:
    """Checks that the AI returned the JSON structure we expect."""

    def validate(self, result: Any, request: FundingRequest) -> tuple[bool, str]:
        if not isinstance(result, dict):
            return False, "AI response is not a JSON object."

        required_fields = ["event_type", "event_purpose", "expenses", "missing_information"]

        for field in required_fields:
            if field not in result:
                return False, f"Missing AI field: {field}"

        if result["event_type"] not in VALID_EVENT_TYPES:
            return False, "Invalid event_type returned by AI."

        if not isinstance(result["event_purpose"], str):
            return False, "event_purpose must be text."

        if not isinstance(result["expenses"], list):
            return False, "expenses must be a list."

        if not isinstance(result["missing_information"], list):
            return False, "missing_information must be a list."

        expected_ids = {expense.expense_id for expense in request.expenses}
        returned_ids = set()

        for expense in result["expenses"]:

            if not isinstance(expense, dict):
                return False, "Each AI expense must be a JSON object."

            for field in ["expense_id", "category", "purpose", "ambiguous"]:
                if field not in expense:
                    return False, f"AI expense is missing: {field}"

            if expense["category"] not in VALID_CATEGORIES:
                return False, (f"Invalid expense category: {expense['category']}")

            if not isinstance(expense["purpose"], str):
                return False, "Expense purpose must be text."

            if not isinstance(expense["ambiguous"], bool):
                return False, "ambiguous must be true or false."

            if expense["expense_id"] in returned_ids:
                return False, "AI returned a duplicate expense ID."

            returned_ids.add(expense["expense_id"])

        if returned_ids != expected_ids:
            return False, ("AI expense IDs do not match the submitted expenses.")

        if not all(isinstance(item, str) for item in result["missing_information"]):
            return False, ("missing_information must contain text only.")

        return True, ""
