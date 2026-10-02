import json
import os
from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
MAX_ATTEMPTS = 3

VALID_EVENT_TYPES = {
    "competition",
    "workshop",
    "social",
    "training",
    "community_service",
    "other",
    "unknown"
}

VALID_CATEGORIES = {
    "food",
    "prize",
    "reusable_equipment",
    "venue",
    "transport",
    "marketing",
    "decoration",
    "other",
    "unknown"
}

AI_INSTRUCTIONS = """
You classify student club funding requests.

Do not approve or reject funding.
Do not apply funding limits.
Only interpret the event and expense descriptions.

Return ONLY valid JSON in this format:

{
  "event_type": "competition|workshop|social|training|community_service|other|unknown",
  "event_purpose": "short description",
  "expenses": [
    {
      "expense_id": "same ID from the input",
      "category": "food|prize|reusable_equipment|venue|transport|marketing|decoration|other|unknown",
      "purpose": "short description",
      "ambiguous": false
    }
  ],
  "missing_information": []
}

Return exactly one result for every expense.
Never invent expense IDs.
If an expense is unclear, use "unknown" and set "ambiguous" to true.
""".strip()


def build_prompt(request):
    """Creates record to send to the AI."""
    ai_input = {
        "event_title": request["event_title"],
        "event_description": request["event_description"],
        "expected_participants": request["expected_participants"],
        "expenses": [
            {"expense_id": expense["expense_id"],"description": expense["description"],"amount": expense["amount"]}
            for expense in request["expenses"]
        ]
    }

    return json.dumps(ai_input, indent=2)
