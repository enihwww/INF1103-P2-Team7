import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

REQUESTS_FILE = os.path.join(DATA_DIR, "requests.json")
POLICY_FILE = os.path.join(DATA_DIR, "policy.json")
BUDGETS_FILE = os.path.join(DATA_DIR, "club_budgets.json")
EXCEL_FILE = os.path.join(DATA_DIR, "ClubFund_Report.xlsx")

def load_requests():
    """Load saved requests."""
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
    """Load and validate the funding policy."""
    try:
        with open(POLICY_FILE, "r", encoding="utf-8") as file:
            policy = json.load(file)

        required_fields = [
            "max_request_amount",
            "minimum_lead_days",
            "food_per_person_limit",
            "max_prize_amount",
            "equipment_quote_threshold",
            "ineligible_categories",
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
            highest_number = max(highest_number, int(request_id[2:]))

    return f"CF{highest_number + 1:04d}"

def get_used_budget(records, club_name, year):
    """Calculate annual budget already committed."""

    total = 0.0

    for record in records:
        same_club = record.get("club_name") == club_name
        same_year = record.get("funding_year") == year
        committed = record.get("budget_committed", False)

        if same_club and same_year and committed:
            total += record.get("budget_amount", 0)

    return round(total, 2)


def get_budget_info(records, budgets, club_name, year):
    """Return annual, used and remaining budget."""

    annual_budget = float(budgets[club_name])
    used_budget = get_used_budget(records, club_name, year)
    remaining_budget = max(annual_budget - used_budget, 0)

    return {
        "annual_budget": round(annual_budget, 2),
        "used_budget": round(used_budget, 2),
        "remaining_budget": round(remaining_budget, 2),
    }


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
        "budget_committed": 0.0,
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

        # AI-failed records now still have an assessment,
        # so their deterministic values are included here.
        summary["total_requested"] += assessment.get("total_requested", 0)

        summary["estimated_eligible"] += assessment.get("estimated_eligible_amount", 0)

        summary["budget_committed"] += record.get("budget_amount", 0)

    for field in ["total_requested", "estimated_eligible", "budget_committed"]:
        summary[field] = round(summary[field], 2)

    return summary


def make_record(request, ai_result, assessment, processing_status, error=None):
    """Combine input, AI output and assessment for saving."""
    record = request.copy()
    record["ai_result"] = ai_result
    record["assessment"] = assessment
    record["processing_status"] = processing_status
    record["processing_error"] = error

    # A failed API request produces MANUAL_REVIEW,
    # so it will never reserve annual budget.
    if (
        assessment
        and assessment["status"] == "READY_FOR_REVIEW"
        and processing_status == "PROCESSED"
    ):
        record["budget_committed"] = True
        record["budget_amount"] = assessment["budget_to_commit"]
    else:
        record["budget_committed"] = False
        record["budget_amount"] = 0.0

    return record


# Exporting to Excel.
def export_to_excel(records, budgets):
    """Create an Excel report from the JSON records."""

    try:
        import xlsxwriter
    except ImportError:
        return False, ("XlsxWriter is not installed.")

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        workbook = xlsxwriter.Workbook(EXCEL_FILE)
        title_format = workbook.add_format({"bold": True, "font_size": 16})
        header_format = workbook.add_format({"bold": True, "border": 1})
        money_format = workbook.add_format({"num_format": "$#,##0.00"})
        percent_format = workbook.add_format({"num_format": "0%"})

        # Dashboard
        dashboard = workbook.add_worksheet("Dashboard")
        summary = build_summary(records)
        dashboard.write("A1", "ClubFund Dashboard", title_format)
        dashboard.write("A3", "Total Requests")
        dashboard.write("B3", summary["total_requests"])
        dashboard.write("A4", "Ready for Review")
        dashboard.write("B4", summary["ready_for_review"])
        dashboard.write("A5", "Revision Required")
        dashboard.write("B5", summary["revision_required"])
        dashboard.write("A6", "Manual Review")
        dashboard.write("B6", summary["manual_review"])
        dashboard.write("A7", "AI Failed")
        dashboard.write("B7", summary["ai_failed"])
        dashboard.write("A9", "Total Requested")
        dashboard.write("B9", summary["total_requested"], money_format)
        dashboard.write("A10", "Estimated / Provisional Eligible")
        dashboard.write("B10", summary["estimated_eligible"], money_format)
        dashboard.write("A11", "Budget Committed")
        dashboard.write("B11", summary["budget_committed"], money_format)
        dashboard.set_column("A:A", 32)
        dashboard.set_column("B:B", 18)

        # Requests
        requests_sheet = workbook.add_worksheet("Requests")

        request_headers = [
            "Request ID",
            "Club",
            "Funding Year",
            "Event",
            "Event Date",
            "Participants",
            "Requested",
            "Estimated / Provisional Eligible",
            "Assessment Status",
            "Processing Status",
            "Budget Committed",
            "Processing Error",
        ]

        for column, header in enumerate(request_headers):
            requests_sheet.write(0, column, header, header_format)

        for row, record in enumerate(records, start=1):
            assessment = record.get("assessment") or {}

            values = [
                record.get("request_id", ""),
                record.get("club_name", ""),
                record.get("funding_year", ""),
                record.get("event_title", ""),
                record.get("event_date", ""),
                record.get("expected_participants", 0),
                assessment.get("total_requested", 0),
                assessment.get("estimated_eligible_amount", 0),
                assessment.get("status", ""),
                record.get("processing_status", ""),
                record.get("budget_amount", 0),
                record.get("processing_error", "") or "",
            ]

            for column, value in enumerate(values):
                if column in (6, 7, 10):
                    requests_sheet.write(row, column, value, money_format)
                else:
                    requests_sheet.write(row, column, value)

        requests_sheet.set_column("A:A", 12)
        requests_sheet.set_column("B:B", 22)
        requests_sheet.set_column("C:C", 12)
        requests_sheet.set_column("D:D", 28)
        requests_sheet.set_column("E:E", 14)
        requests_sheet.set_column("F:F", 12)
        requests_sheet.set_column("G:K", 22)
        requests_sheet.set_column("L:L", 50)

        # Expenses
        expenses_sheet = workbook.add_worksheet("Expenses")

        expense_headers = [
            "Request ID",
            "Club",
            "Year",
            "Expense ID",
            "Description",
            "AI Category",
            "Amount",
            "Quote Available",
        ]

        for column, header in enumerate(expense_headers):
            expenses_sheet.write(0, column, header, header_format)

        expense_row = 1

        for record in records:
            ai_result = record.get("ai_result") or {}

            ai_expenses = {
                item["expense_id"]: item
                for item in ai_result.get("expenses", [])
                if "expense_id" in item
            }

            for expense in record.get("expenses", []):
                ai_expense = ai_expenses.get(expense["expense_id"], {})

                values = [
                    record.get("request_id", ""),
                    record.get("club_name", ""),
                    record.get("funding_year", ""),
                    expense.get("expense_id", ""),
                    expense.get("description", ""),
                    ai_expense.get("category", ""),
                    expense.get("amount", 0),
                    ("Yes" if expense.get("quote_available") else "No"),
                ]

                for column, value in enumerate(values):
                    if column == 6:
                        expenses_sheet.write(expense_row, column, value, money_format)
                    else:
                        expenses_sheet.write(expense_row, column, value)

                expense_row += 1

        expenses_sheet.set_column("A:D", 14)
        expenses_sheet.set_column("E:E", 35)
        expenses_sheet.set_column("F:F", 22)
        expenses_sheet.set_column("G:G", 14)
        expenses_sheet.set_column("H:H", 16)

        # Annual Budgets
        budget_sheet = workbook.add_worksheet("Annual Budgets")

        budget_headers = [
            "Club",
            "Year",
            "Annual Budget",
            "Used / Committed",
            "Remaining",
            "% Used",
        ]

        for column, header in enumerate(budget_headers):
            budget_sheet.write(0, column, header, header_format)

        years = sorted(
            {
                record.get("funding_year")
                for record in records
                if record.get("funding_year") is not None
            }
        )

        budget_row = 1

        for year in years:
            for club in get_club_names(budgets):
                info = get_budget_info(records, budgets, club, year)

                percent_used = 0

                if info["annual_budget"] > 0:
                    percent_used = info["used_budget"] / info["annual_budget"]

                budget_sheet.write(budget_row, 0, club)
                budget_sheet.write(budget_row, 1, year)
                budget_sheet.write(budget_row, 2, info["annual_budget"], money_format)
                budget_sheet.write(budget_row, 3, info["used_budget"], money_format)
                budget_sheet.write(
                    budget_row, 4, info["remaining_budget"], money_format
                )
                budget_sheet.write(budget_row, 5, percent_used, percent_format)

                budget_row += 1

        budget_sheet.set_column("A:A", 24)
        budget_sheet.set_column("B:B", 10)
        budget_sheet.set_column("C:E", 18)
        budget_sheet.set_column("F:F", 12)
        workbook.close()

        return True, (f"Excel report created: " f"{EXCEL_FILE}")

    except Exception as error:
        return False, (f"Could not create Excel report: " f"{error}")