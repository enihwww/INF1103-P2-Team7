from __future__ import annotations

import os


MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

MAX_ATTEMPTS = 3

REQUEST_TIMEOUT = 30  # seconds before one API call is treated as failed

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
