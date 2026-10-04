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

# Return club names
def get_club_names(budgets):
    """Return club names in alphabetical order."""
    return sorted(budgets.keys())

def next_request_id(records):
    """Generate CF0001, CF0002, CF0003, etc."""
    highest_number = 0

    for record in records:
        request_id = record.get("request_id", "")

        if request_id.startswith("CF") and request_id[2:].isdigit():
            highest_number = max(
                highest_number,
                int(request_id[2:])
            )

    return f"CF{highest_number + 1:04d}"

def get_used_budget(records, club_name, year):
    """Calculate how much annual budget has already been committed.

    Only requests marked budget_committed=True are counted.
    Requests from other years do not affect this year's budget.
    """
    total = 0.0

    for record in records:
        same_club = record.get("club_name") == club_name
        same_year = record.get("funding_year") == year
        committed = record.get("budget_committed", False)

        if same_club and same_year and committed:
            total += record.get("budget_amount", 0)

    return round(total, 2)

# Calculate annual budget, amount already used and amount remaining.
def get_budget_info(records, budgets, club_name, year):
    """Return annual, used and remaining budget for one club and year."""
    annual_budget = float(budgets[club_name])
    used_budget = get_used_budget(records,club_name,year)
    remaining_budget = max(annual_budget - used_budget,0)

    return {"annual_budget": round(annual_budget, 2),
        "used_budget": round(used_budget, 2),
        "remaining_budget": round(remaining_budget, 2)}

def build_summary(records):
    """Calculate statistics for the summary menu."""
    summary = {
        "total_requests": len(records),
        "ready_for_review": 0,
        "revision_required": 0,
        "manual_review": 0,
        "ai_failed": 0,
        "total_requested": 0.0,
        "estimated_eligible": 0.0,
        "budget_committed": 0.0
    }

    for record in records:
        assessment = record.get("assessment") or {}
        status = assessment.get("status")
        if status == "READY_FOR_REVIEW":
            summary["ready_for_review"] += 1

        elif status == "REVISION_REQUIRED":
            summary["revision_required"] += 1

        elif status == "MANUAL_REVIEW":
            summary["manual_review"] += 1

        if record.get("processing_status") == "AI_FAILED":
            summary["ai_failed"] += 1

        summary["total_requested"] += assessment.get("total_requested",0)
        summary["estimated_eligible"] += assessment.get("estimated_eligible_amount",0)
        summary["budget_committed"] += record.get("budget_amount",0)

    for field in ["total_requested","estimated_eligible","budget_committed"]:
        summary[field] = round(summary[field], 2)

    return summary


def make_record(request,ai_result,assessment,processing_status,error=None):
    """Combine input, AI output and assessment for saving."""
    record = request.copy()
    record["ai_result"] = ai_result
    record["assessment"] = assessment
    record["processing_status"] = processing_status
    record["processing_error"] = error

    # READY_FOR_REVIEW automatically reserves the eligible amount.
    if assessment and assessment["status"] == "READY_FOR_REVIEW":
        record["budget_committed"] = True
        record["budget_amount"] = assessment["budget_to_commit"]
    else:
        record["budget_committed"] = False
        record["budget_amount"] = 0.0

    return record