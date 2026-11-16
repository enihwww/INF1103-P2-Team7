from __future__ import annotations

import os
from typing import Any

from models import FundingRecord, JsonDict
from .budget_ledger import BudgetLedger


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
