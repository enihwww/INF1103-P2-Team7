from __future__ import annotations

from models import FundingRequest, JsonDict
from .ai_classifier import AIClassifier


class FallbackClassifier(AIClassifier):
    """Safe result when the live AI service is unavailable.

    This is NOT an AI replacement. All AI-dependent fields are marked
    unknown/ambiguous so the logic manager sends the request to MANUAL_REVIEW.
    """

    def classify(self, request: FundingRequest) -> JsonDict:
        expenses = []

        for expense in request.expenses:
            expenses.append({
                "expense_id": expense.expense_id,
                "category": "unknown",
                "purpose": "Not classified because AI service was unavailable.",
                "ambiguous": True
            })

        return {
            "event_type": "unknown",
            "event_purpose": ("Not classified because AI service was unavailable."),
            "expenses": expenses,
            "missing_information": ["AI classification unavailable. Manual review is required."]
        }
