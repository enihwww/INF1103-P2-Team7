import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

REQUESTS_FILE = os.path.join(DATA_DIR, "requests.json")
POLICY_FILE = os.path.join(DATA_DIR, "policy.json")
BUDGETS_FILE = os.path.join(DATA_DIR, "club_budgets.json")
EXCEL_FILE = os.path.join(DATA_DIR, "ClubFund_Report.xlsx")

def load_requests():
    """Load saved requests. A missing file means no requests yet."""
    if not os.path.exists(REQUESTS_FILE):
        return [], None

    try:
        with open(REQUESTS_FILE, "r", encoding="utf-8") as file:
            records = json.load(file)

        if not isinstance(records, list):
            return [], "requests.json must contain a list."

        return records, None

    except (OSError, json.JSONDecodeError) as error:
        return [], f"Could not load requests: {error}"
