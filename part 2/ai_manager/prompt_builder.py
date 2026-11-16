from __future__ import annotations

import json

from models import FundingRequest


class PromptBuilder:
    """Creates the record that is sent to the AI."""

    def build(self, request: FundingRequest) -> str:
        ai_input = {
            "event_title": request.event_title,
            "event_description": request.event_description,
            "expected_participants": request.expected_participants,
            "expenses": [
                {
                    "expense_id": expense.expense_id,
                    "description": expense.description,
                    "amount": expense.amount
                }
                for expense in request.expenses
            ]
        }

        return json.dumps(ai_input, indent=2)
