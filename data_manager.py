from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

from models import Assessment, BudgetInfo, FundingRecord, FundingRequest, JsonDict, Policy, PolicyError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

REQUESTS_FILE = os.path.join(DATA_DIR, "requests.json")
POLICY_FILE = os.path.join(DATA_DIR, "policy.json")
BUDGETS_FILE = os.path.join(DATA_DIR, "club_budgets.json")
EXCEL_FILE = os.path.join(DATA_DIR, "ClubFund_Report.xlsx")

# Interface for loading and saving one kind of data
class Repository(ABC):

    @abstractmethod
    def load(self) -> tuple[Any, str | None]:
        """Return (data, error_message)."""

    @abstractmethod
    def save(self, data: Any) -> tuple[bool, str | None]:
        """Return (success, error_message)."""

# Saves and loads request records in requests.json
class JsonRequestRepository(Repository):

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path

    def load(self) -> tuple[list[FundingRecord], str | None]:
        if not os.path.exists(self._file_path):
            return [], None

        try:
            with open(self._file_path, "r", encoding="utf-8") as file:
                records = json.load(file)

            if not isinstance(records, list):
                return [], "requests.json must contain a list."

            return [FundingRecord.from_dict(record) for record in records], None

        except (OSError, json.JSONDecodeError) as error:
            return [], f"Could not load requests: {error}"

        except (AttributeError, TypeError, ValueError) as error:
            return [], f"Could not load requests: a saved record is corrupt ({error})."

    def save(self, records: list[FundingRecord]) -> tuple[bool, str | None]:
        try:
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)

            with open(self._file_path, "w", encoding="utf-8") as file:
                json.dump([record.to_dict() for record in records], file, indent=2)

            return True, None

        except OSError as error:
            return False, f"Could not save requests: {error}"

# Saves and loads the funding policy in policy.json
class JsonPolicyRepository(Repository):

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path

    def load(self) -> tuple[Policy | None, str | None]:
        try:
            with open(self._file_path, "r", encoding="utf-8") as file:
                return Policy.from_dict(json.load(file)), None

        except FileNotFoundError:
            return None, "policy.json was not found."

        except (OSError, json.JSONDecodeError) as error:
            return None, f"Could not load policy: {error}"

        except PolicyError as error:
            return None, str(error)

    def save(self, policy: Policy) -> tuple[bool, str | None]:
        try:
            with open(self._file_path, "w", encoding="utf-8") as file:
                json.dump(policy.to_dict(), file, indent=2)

            return True, None

        except OSError as error:
            return False, f"Could not save policy: {error}"

# Loads the fixed annual allocation for each club (read only)
class JsonBudgetRepository:

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path

    def load(self) -> tuple[dict[str, float] | None, str | None]:
        try:
            with open(self._file_path, "r", encoding="utf-8") as file:
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

# Works out used and remaining budget from the saved records
class BudgetLedger:

    def __init__(self, budgets: dict[str, float], records: list[FundingRecord]) -> None:
        # Aggregation: the records list belongs to the DataManager and is shared here
        self._budgets = budgets
        self._records = records

    # Calculate annual budget already committed
    def get_used_budget(self, club_name: str, year: int | None) -> float:
        total = 0.0

        for record in self._records:
            same_club = record.club_name == club_name
            same_year = record.funding_year == year

            if same_club and same_year and record.budget_committed:
                total += record.budget_amount

        return round(total, 2)

    # Return annual, used and remaining budget
    def get_budget_info(self, club_name: str, year: int | None) -> BudgetInfo:
        annual_budget = float(self._budgets[club_name])
        used_budget = self.get_used_budget(club_name, year)
        remaining_budget = max(annual_budget - used_budget, 0)

        return {
            "annual_budget": round(annual_budget, 2),
            "used_budget": round(used_budget, 2),
            "remaining_budget": round(remaining_budget, 2),
        }

# Creates an Excel report from the saved records
class ExcelReportExporter:

    def export(self, file_path: str, records: list[FundingRecord], budgets: dict[str, float], ledger: BudgetLedger, summary: JsonDict) -> tuple[bool, str]:
        try:
            import xlsxwriter
        except ImportError:
            return False, ("XlsxWriter is not installed.")

        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            workbook = xlsxwriter.Workbook(file_path)
            formats = {
                "title": workbook.add_format({"bold": True, "font_size": 16}),
                "header": workbook.add_format({"bold": True, "border": 1}),
                "money": workbook.add_format({"num_format": "$#,##0.00"}),
                "percent": workbook.add_format({"num_format": "0%"}),
            }
            rows = [record.to_dict() for record in records]

            self._write_dashboard(workbook, formats, summary)
            self._write_requests(workbook, formats, rows)
            self._write_expenses(workbook, formats, rows)
            self._write_budgets(workbook, formats, rows, budgets, ledger)
            workbook.close()

            return True, (f"Excel report created: " f"{file_path}")

        except Exception as error:
            return False, (f"Could not create Excel report: " f"{error}")

    def _write_dashboard(self, workbook: Any, formats: dict[str, Any], summary: JsonDict) -> None:
        dashboard = workbook.add_worksheet("Dashboard")
        dashboard.write("A1", "ClubFund Dashboard", formats["title"])
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
        dashboard.write("B9", summary["total_requested"], formats["money"])
        dashboard.write("A10", "Estimated / Provisional Eligible")
        dashboard.write("B10", summary["estimated_eligible"], formats["money"])
        dashboard.write("A11", "Budget Committed")
        dashboard.write("B11", summary["budget_committed"], formats["money"])
        dashboard.set_column("A:A", 32)
        dashboard.set_column("B:B", 18)

    def _write_requests(self, workbook: Any, formats: dict[str, Any], rows: list[JsonDict]) -> None:
        requests_sheet = workbook.add_worksheet("Requests")

        request_headers = [
            "Request ID", "Club", "Funding Year", "Event", "Event Date", "Participants",
            "Requested", "Estimated / Provisional Eligible", "Assessment Status",
            "Processing Status", "Budget Committed", "Processing Error",
        ]

        for column, header in enumerate(request_headers):
            requests_sheet.write(0, column, header, formats["header"])

        for row, record in enumerate(rows, start=1):
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
                    requests_sheet.write(row, column, value, formats["money"])
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

    def _write_expenses(self, workbook: Any, formats: dict[str, Any], rows: list[JsonDict]) -> None:
        expenses_sheet = workbook.add_worksheet("Expenses")

        expense_headers = [
            "Request ID", "Club", "Year", "Expense ID",
            "Description", "AI Category", "Amount", "Quote Available",
        ]

        for column, header in enumerate(expense_headers):
            expenses_sheet.write(0, column, header, formats["header"])

        expense_row = 1

        for record in rows:
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
                        expenses_sheet.write(expense_row, column, value, formats["money"])
                    else:
                        expenses_sheet.write(expense_row, column, value)

                expense_row += 1

        expenses_sheet.set_column("A:D", 14)
        expenses_sheet.set_column("E:E", 35)
        expenses_sheet.set_column("F:F", 22)
        expenses_sheet.set_column("G:G", 14)
        expenses_sheet.set_column("H:H", 16)

    def _write_budgets(self, workbook: Any, formats: dict[str, Any], rows: list[JsonDict], budgets: dict[str, float], ledger: BudgetLedger) -> None:
        budget_sheet = workbook.add_worksheet("Annual Budgets")

        budget_headers = ["Club", "Year", "Annual Budget", "Used / Committed", "Remaining", "% Used"]

        for column, header in enumerate(budget_headers):
            budget_sheet.write(0, column, header, formats["header"])

        year_values: set[int] = {
            record["funding_year"]
            for record in rows
            if record.get("funding_year") is not None
        }
        years = sorted(year_values)

        budget_row = 1

        for year in years:
            for club in sorted(budgets.keys()):
                info = ledger.get_budget_info(club, year)

                percent_used = 0.0

                if info["annual_budget"] > 0:
                    percent_used = info["used_budget"] / info["annual_budget"]

                budget_sheet.write(budget_row, 0, club)
                budget_sheet.write(budget_row, 1, year)
                budget_sheet.write(budget_row, 2, info["annual_budget"], formats["money"])
                budget_sheet.write(budget_row, 3, info["used_budget"], formats["money"])
                budget_sheet.write(budget_row, 4, info["remaining_budget"], formats["money"])
                budget_sheet.write(budget_row, 5, percent_used, formats["percent"])

                budget_row += 1

        budget_sheet.set_column("A:A", 24)
        budget_sheet.set_column("B:B", 10)
        budget_sheet.set_column("C:E", 18)
        budget_sheet.set_column("F:F", 12)

# Single entry point for saving, loading and summarising ClubFund data
class DataManager:

    def __init__(self, data_dir: str = DATA_DIR) -> None:
        self._data_dir = data_dir
        # Composition: the data manager creates and owns its repositories and exporter.
        self._request_repository = JsonRequestRepository(os.path.join(data_dir, "requests.json"))
        self._policy_repository = JsonPolicyRepository(os.path.join(data_dir, "policy.json"))
        self._budget_repository = JsonBudgetRepository(os.path.join(data_dir, "club_budgets.json"))
        self._exporter = ExcelReportExporter()
        self.excel_file = os.path.join(data_dir, "ClubFund_Report.xlsx")

        self._records: list[FundingRecord] = []
        self._policy: Policy | None = None
        self._budgets: dict[str, float] = {}
        self._ledger = BudgetLedger(self._budgets, self._records)

    # Load saved requests from previous program runs
    def load_requests(self) -> str | None:
        records, error = self._request_repository.load()
        self._records[:] = records  # keep the same list object shared with the ledger
        return error

    def load_policy(self) -> str | None:
        self._policy, error = self._policy_repository.load()
        return error

    def load_club_budgets(self) -> str | None:
        budgets, error = self._budget_repository.load()
        self._budgets.clear()
        if budgets:
            self._budgets.update(budgets)
        return error

    @property
    def records(self) -> list[FundingRecord]:
        return list(self._records)

    @property
    def policy(self) -> Policy:
        if self._policy is None:
            raise RuntimeError("The funding policy has not been loaded.")
        return self._policy

    @property
    def budgets(self) -> dict[str, float]:
        return dict(self._budgets)

    # Return club names in alphabetical order
    def get_club_names(self) -> list[str]:
        return sorted(self._budgets.keys())
    
    # Records of one club only (what a student is allowed to see)
    def records_for_club(self, club_name: str) -> list[FundingRecord]:
        return [record for record in self._records if record.club_name == club_name]

    def find_record(self, request_id: str) -> FundingRecord | None:
        for record in self._records:
            if record.request_id == request_id:
                return record
        return None

    # Generate CF0001, CF0002, CF0003, etc...
    def next_request_id(self) -> str:
        highest_number = 0

        for record in self._records:
            request_id = record.request_id or ""

            if request_id.startswith("CF") and request_id[2:].isdigit():
                highest_number = max(highest_number, int(request_id[2:]))

        return f"CF{highest_number + 1:04d}"

    def get_budget_info(self, club_name: str, year: int | None) -> BudgetInfo:
        return self._ledger.get_budget_info(club_name, year)

    # Combine input, AI output and assessment for saving
    def make_record(self, request: FundingRequest, ai_result: JsonDict | None, assessment: Assessment | None, processing_status: str, error: str | None = None) -> FundingRecord:
        # A failed API request produces MANUAL_REVIEW, so it will never reserve annual budget.
        if (
            assessment
            and assessment.status == Assessment.READY
            and processing_status == FundingRecord.PROCESSED
        ):
            return FundingRecord(request, ai_result, assessment, processing_status, error,
                                 True, assessment.budget_to_commit)

        return FundingRecord(request, ai_result, assessment, processing_status, error, False, 0.0)

    # Add one record and save the updated list
    def add_request(self, record: FundingRecord) -> tuple[bool, str | None]:
        self._records.append(record)
        success, error = self._request_repository.save(self._records)

        if not success:
            self._records.pop()

        return success, error

    # ADMIN Feature! Validate, save and apply new policy values
    def update_policy(self, changes: JsonDict) -> tuple[bool, str]:
        """The live policy only changes after the file is saved, so the
        program and policy.json never disagree."""
        try:
            candidate = Policy.from_dict(self.policy.to_dict())
            candidate.update(changes)
        except PolicyError as error:
            return False, str(error)

        saved, save_error = self._policy_repository.save(candidate)
        if not saved:
            return False, save_error or "Could not save policy."

        # Update the shared object so the logic manager uses the new values straight away.
        self.policy.update(candidate.to_dict())
        return True, "Funding policy updated."

    # Calculate statistics for the summary menu
    def build_summary(self, records: list[FundingRecord] | None = None) -> JsonDict:
        if records is None:
            records = self._records

        summary: JsonDict = {
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
            assessment = record.assessment
            status = assessment.status if assessment else None

            if status == Assessment.READY:
                summary["ready_for_review"] += 1

            elif status == Assessment.REVISION:
                summary["revision_required"] += 1

            elif status == Assessment.MANUAL:
                summary["manual_review"] += 1

            if record.processing_status == FundingRecord.AI_FAILED:
                summary["ai_failed"] += 1

            # AI-failed records still have an assessment, so their deterministic values are included here.
            if assessment:
                summary["total_requested"] += assessment.total_requested
                summary["estimated_eligible"] += assessment.estimated_eligible_amount

            summary["budget_committed"] += record.budget_amount

        for field in ["total_requested", "estimated_eligible", "budget_committed"]:
            summary[field] = round(summary[field], 2)

        return summary

    # Create an Excel report from the JSON records
    def export_to_excel(self, records: list[FundingRecord] | None = None, file_path: str | None = None) -> tuple[bool, str]:
        if records is None:
            records = self._records
        if file_path is None:
            file_path = self.excel_file

        ledger = BudgetLedger(self._budgets, records)
        summary = self.build_summary(records)
        return self._exporter.export(file_path, records, self._budgets, ledger, summary)


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