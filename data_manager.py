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

def save_requests(records):
    """Save all request records to JSON."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)

        with open(REQUESTS_FILE, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)

        return True, None

    except OSError as error:
        return False, f"Could not save requests: {error}"

def add_request(records, record):
    """Add one record and save the updated list."""
    records.append(record)
    success, error = save_requests(records)

    if not success:
        records.pop()

    return success, error

def load_policy():
    """Load and lightly validate the funding policy."""
    try:
        with open(POLICY_FILE, "r", encoding="utf-8") as file:
            policy = json.load(file)

        required_fields = [
            "max_request_amount",
            "minimum_lead_days",
            "food_per_person_limit",
            "max_prize_amount",
            "equipment_quote_threshold",
            "ineligible_categories"
        ]

        for field in required_fields:
            if field not in policy:
                return None, f"Policy is missing: {field}"

        return policy, None

    except FileNotFoundError:
        return None, "policy.json was not found."

    except (OSError, json.JSONDecodeError) as error:
        return None, f"Could not load policy: {error}"

# ============================================================
# NEW: Load and validate each club's fixed annual allocation.
# ============================================================
def load_club_budgets():
    """Load the fixed annual allocation for each club."""
    try:
        with open(BUDGETS_FILE, "r", encoding="utf-8") as file:
            budgets = json.load(file)

        if not isinstance(budgets, dict) or not budgets:
            return None, "club_budgets.json must contain club budgets."

        for club, amount in budgets.items():
            if not isinstance(club, str):
                return None, "Club names in club_budgets.json must be text."

            if not isinstance(amount, (int, float)) or amount < 0:
                return None, f"Invalid annual budget for {club}."

        return budgets, None

    except FileNotFoundError:
        return None, "club_budgets.json was not found."

    except (OSError, json.JSONDecodeError) as error:
        return None, f"Could not load club budgets: {error}"
