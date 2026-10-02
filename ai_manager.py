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


def validate_result(result, request):
    """Checks if AI returned the correct JSON structure."""
    if not isinstance(result, dict):
        return False, "AI response is not a JSON object."

    required_fields = [
        "event_type",
        "event_purpose",
        "expenses",
        "missing_information"
    ]

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

    expected_ids = {
        expense["expense_id"]
        for expense in request["expenses"]
    }

    returned_ids = set()

    for expense in result["expenses"]:
        if not isinstance(expense, dict):
            return False, "Each AI expense must be a JSON object."

        for field in ["expense_id", "category", "purpose", "ambiguous"]:
            if field not in expense:
                return False, f"AI expense is missing: {field}"

        if expense["category"] not in VALID_CATEGORIES:
            return False, f"Invalid expense category: {expense['category']}"

        if not isinstance(expense["purpose"], str):
            return False, "Expense purpose must be text."

        if not isinstance(expense["ambiguous"], bool):
            return False, "ambiguous must be true or false."

        if expense["expense_id"] in returned_ids:
            return False, "AI returned a duplicate expense ID."

        returned_ids.add(expense["expense_id"])

    if returned_ids != expected_ids:
        return False, "AI expense IDs do not match the submitted expenses."

    if not all(
        isinstance(item, str)
        for item in result["missing_information"]
    ):
        return False, "missing_information must contain text only."

    return True, ""


def analyse_request(request):
    """Send a funding request to the AI and return validated JSON."""
    prompt = build_prompt(request)
    last_error = "Unknown AI error."

    for _ in range(MAX_ATTEMPTS):
        try:
            client = OpenAI()

            response = client.responses.create(
                model=MODEL,
                instructions=AI_INSTRUCTIONS,
                input=prompt
            )

            result = json.loads(response.output_text)
            valid, error = validate_result(result, request)

            if valid:
                return result, None

            last_error = error

        except Exception as error:
            last_error = str(error)

    return None, (
        f"AI processing failed after {MAX_ATTEMPTS} attempts: "
        f"{last_error}"
    )
