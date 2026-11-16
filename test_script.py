from __future__ import annotations

import json
import os

from ai_manager import AIManager, FallbackClassifier
from data_manager import BudgetLedger, DataManager
from io_manager import ConsoleIO
from logic_manager import LogicManager
from models import Assessment, FundingRecord, FundingRequest, JsonDict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_CASES_FILE = os.path.join(BASE_DIR, "data", "test_cases.json")


class OfflineTestRunner:
    """Runs the predetermined cases in test_cases.json one at a time from a menu."""

    def __init__(self, io: ConsoleIO, data_manager: DataManager) -> None:
        self._io = io
        self._data_manager = data_manager
        # The stored AI results are validated with the same AI manager used by the app.
        self._ai_manager = AIManager(FallbackClassifier())
        self._test_cases: list[JsonDict] = []
        # Store the latest processed test result in memory.
        self._last_test_result: FundingRecord | None = None

    def load_test_cases(self) -> str | None:
        """Load offline test data from JSON."""
        try:
            with open(TEST_CASES_FILE, "r", encoding="utf-8") as file:
                test_cases = json.load(file)

            if not isinstance(test_cases, list):
                return "test_cases.json must contain a list."
            self._test_cases = test_cases
            return None
        except FileNotFoundError:
            return "data/test_cases.json was not found."

        except (OSError, json.JSONDecodeError) as error:
            return f"Could not load test cases: {error}"

    def show_test_case_parameters(self) -> None:
        # Show all JSON parameters.
        show = self._io.show_message
        show("\n=== OFFLINE TEST PARAMETERS ===")
        show("The following values are loaded directly from data/test_cases.json.\n")

        for number, test_case in enumerate(self._test_cases, start=1):
            request = test_case["request"]
            ai_result = test_case["ai_result"]
            expected = test_case["expected"]
            existing_records = test_case.get("existing_records", [])
            show(f"\nOption {number} parameters:")

            # Request input
            show("\nRequest input:")
            show(f"  Request ID: {request['request_id']}")
            show(f"  Club: {request['club_name']}")
            show(f"  Event title: {request['event_title']}")
            show(f"  Event description: {request['event_description']}")
            show(f"  Event date: {request['event_date']}")
            show(f"  Submission date: {request['submission_date']}")
            show(f"  Expected participants: {request['expected_participants']}")
            show(f"  Funding year: {request['funding_year']}")
            show("  Expenses:")
            for expense in request["expenses"]:
                quote_text = "Yes" if expense["quote_available"] else "No"
                show(f"{expense['expense_id']}: {expense['description']} | "
                     f"${expense['amount']:.2f} | Supplier quote: {quote_text}")

            show("\nAI result:")
            show(f"  Event type: {ai_result['event_type']}")
            show(f"  Event purpose: {ai_result['event_purpose']}")
            show("  AI expense classifications:")
            for ai_expense in ai_result["expenses"]:
                ambiguous_text = "Yes" if ai_expense["ambiguous"] else "No"
                show(f"{ai_expense['expense_id']}: Category = {ai_expense['category']} | "
                     f"Purpose = {ai_expense['purpose']} | Ambiguous = {ambiguous_text}")

            if ai_result["missing_information"]:
                show("  Missing information:")
                for item in ai_result["missing_information"]:
                    show(f"    - {item}")
            else:
                show("  Missing information: None")

            show("\nExisting budget/history records:")
            if existing_records:
                for record in existing_records:
                    show(f"  {record.get('request_id', '-')}: {record.get('club_name', '-')} | "
                         f"Year {record.get('funding_year', '-')} | "
                         f"Committed = {record.get('budget_committed', False)} | "
                         f"Amount = ${record.get('budget_amount', 0):.2f}")
            else:
                show("None")

            show("\nExpected output:")
            for field, value in expected.items():
                if isinstance(value, float):
                    display_value = (f"${value:.2f}"
                        if "amount" in field or "total" in field or "commit" in field
                        else f"{value:.2f}")
                else:
                    display_value = value
                readable_field = field.replace("_", " ").title()
                show(f"  {readable_field}: {display_value}")
            show("")
        show("\nEnd of test data.")

    def show_test_menu(self) -> None:
        # Displays test menu.
        self._io.show_message("\n=== CLUBFUND TESTS ===")
        for number, test_case in enumerate(self._test_cases, start=1):
            self._io.show_message(f"{number}. {test_case['name']}")
        self._io.show_message("6. Export last test result to Excel")
        self._io.show_message("7. Exit")

    def get_menu_choice(self) -> int:
        while True:
            choice = self._io.get_positive_int("Select option: ")
            if 1 <= choice <= 7:
                return choice
            self._io.show_message("Invalid option. Enter 1-7.")

    @staticmethod
    def compare_expected(assessment: Assessment, expected: JsonDict) -> list[str]:
        """Check selected output values against the expected result."""
        differences = []
        values = assessment.to_dict()
        for field, expected_value in expected.items():
            actual_value = values.get(field)
            if isinstance(expected_value, float):
                if actual_value is not None:
                    actual_value = round(float(actual_value), 2)

            if actual_value != expected_value:
                differences.append(f"{field}: expected {expected_value}, got {actual_value}")
        return differences

    def run_test_case(self, test_case: JsonDict) -> FundingRecord | None:
        """Run one predetermined request through the normal managers."""
        request = FundingRequest.from_dict(test_case["request"])
        ai_result = test_case["ai_result"]

        # 1. AI MANAGER - validate the predetermined AI response.
        valid, error = self._ai_manager.validate_result(ai_result, request)
        if not valid:
            self._io.show_message("\nTest could not continue because the AI result is invalid.")
            self._io.show_message(f"Reason: {error}")
            return None

        # 2. DATA MANAGER - some test cases include previous records so annual budget can also be tested.
        existing_records = [FundingRecord.from_dict(record) for record in test_case.get("existing_records", [])]
        budget_info = BudgetLedger(self._data_manager.budgets, existing_records).get_budget_info(
            request.club_name, request.funding_year)

        # 3. LOGIC MANAGER
        logic_manager = LogicManager(self._data_manager.policy, LogicManager.default_rules())
        assessment = logic_manager.assess_request(request, ai_result, budget_info)

        # 4. DATA MANAGER - same record structure used by main.py. Not written to requests.json.
        processed_record = self._data_manager.make_record(request, ai_result, assessment, FundingRecord.PROCESSED)

        # 5. I/O MANAGER - display exactly the same funding assessment as main.py.
        self._io.show_result(processed_record)
        differences = self.compare_expected(assessment, test_case["expected"])
        if not differences:
            self._io.show_message("\nTEST RESULT: PASS")
        else:
            self._io.show_message("\nTEST RESULT: FAIL")
            for difference in differences:
                self._io.show_message(f"- {difference}")
        return processed_record

    def export_test_result(self) -> None:
        """Export the most recent test to a separate Excel file."""
        if self._last_test_result is None:
            self._io.show_message("\nNo test result is available yet.")
            self._io.show_message("Run one of the test cases first.")
            return

        # Keep the normal main.py report unchanged by using a separate file name.
        test_excel_file = os.path.join(BASE_DIR, "data", "ClubFund_Test_Report.xlsx")
        success, message = self._data_manager.export_to_excel([self._last_test_result], test_excel_file)
        self._io.show_message(message)

    def run(self) -> None:
        error = self.load_test_cases()
        if error:
            self._io.show_message(error)
            return

        # Shows parameters from test_cases.json
        self.show_test_case_parameters()

        while True:
            self.show_test_menu()
            choice = self.get_menu_choice()
            if 1 <= choice <= 5:
                test_case = self._test_cases[choice - 1]
                self._io.show_message(test_case["name"])
                self._last_test_result = self.run_test_case(test_case)
            # Export the most recently run test.
            elif choice == 6:
                self.export_test_result()
            # Exit
            elif choice == 7:
                self._io.show_message("Offline test runner closed.")
                break


if __name__ == "__main__":
    console = ConsoleIO()
    data = DataManager()
    load_error = data.load_policy() or data.load_club_budgets()

    if load_error:
        console.show_message(load_error)
    else:
        OfflineTestRunner(console, data).run()
