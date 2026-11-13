from __future__ import annotations

from datetime import date
from getpass import getpass

from models import (LOCKED_RULES, RULE_NAMES, VALID_CATEGORIES, BudgetInfo, FundingRecord, FundingRequest,
                    JsonDict, Policy)


class ConsoleIO:
    """All terminal input and output for the command-line version."""

    def get_user_role(self) -> str | None:
        # Display the login role selection menu.
        print("\n=== LOG IN ===")
        print("1. Student")
        print("2. Admin")
        print("3. Exit")

        while True:
            choice = input("Choose 1-3: ").strip()

            if choice == "1":
                return "student"

            if choice == "2":
                return "admin"

            if choice == "3":
                return None

            print("Invalid choice. Enter 1, 2 or 3.")

    def get_password(self, prompt: str) -> str:
        # Read a password without showing it on screen.
        return getpass(prompt)

    def show_menu(self, title: str, options: list[str]) -> None:
        # Display a numbered menu built from the options for this role.
        print(f"\n=== {title} ===")

        for number, option in enumerate(options, start=1):
            print(f"{number}. {option}")

    def get_choice(self, number_of_options: int) -> int:
        # Get a valid menu choice from 1 to the number of options.
        while True:
            choice = input(f"Choose 1-{number_of_options}: ").strip()

            if choice.isdigit() and 1 <= int(choice) <= number_of_options:
                return int(choice)

            print(f"Invalid choice. Enter a number from 1 to {number_of_options}.")

    def get_text(self, prompt: str) -> str:
        # Get text that cannot be empty.
        while True:
            value = input(prompt).strip()

            if value:
                return value

            print("Input cannot be empty.")

    def get_positive_int(self, prompt: str) -> int:
        # Get a whole number greater than 0.
        while True:
            value = input(prompt).strip()

            if value.isdigit() and int(value) > 0:
                return int(value)

            print("Enter a whole number greater than 0.")

    def get_money(self, prompt: str) -> float:
        # Get a money value of 0 or more.
        while True:
            try:
                value = float(input(prompt).strip())

                if value >= 0:
                    return round(value, 2)

            except ValueError:
                pass

            print("Enter a valid amount, e.g. 250 or 250.50.")

    def get_yes_no(self, prompt: str) -> bool:
        # Return True for yes and False for no.
        while True:
            answer = input(f"{prompt} (y/n): ").strip().lower()

            if answer in ("y", "yes"):
                return True

            if answer in ("n", "no"):
                return False

            print("Enter y or n.")

    def get_date(self, prompt: str) -> str:
        # Get a valid date in YYYY-MM-DD format.
        while True:
            value = input(f"{prompt} (YYYY-MM-DD): ").strip()

            try:
                date.fromisoformat(value)
                return value

            except ValueError:
                print("Invalid date. Example: 2026-10-15.")

    def select_club(self, club_names: list[str]) -> str:
        # Let the user choose from registered clubs.
        print("\nAvailable clubs:")

        for number, club in enumerate(club_names, start=1):
            print(f"{number}. {club}")

        while True:
            choice = input("Select club: ").strip()

            if choice.isdigit():
                number = int(choice)

                if 1 <= number <= len(club_names):
                    return club_names[number - 1]

            print("Invalid club selection.")

    def collect_request(self, request_id: str, club_name: str) -> FundingRequest:
        # Collect one complete funding request for the student's own club.
        print("\n--- New Funding Request ---")
        print(f"Club: {club_name}")

        request = FundingRequest(
            request_id,
            club_name,
            self.get_text("Event title: "),
            self.get_text("Describe the event: "),
            self.get_date("Event date"),
            self.get_date("Submission date"),
            self.get_positive_int("Expected participants: ")
        )

        number_of_expenses = self.get_positive_int("Number of expense items: ")

        for number in range(1, number_of_expenses + 1):
            print(f"\nExpense {number}")

            request.add_expense(
                self.get_text("Description: "),
                self.get_money("Amount ($): "),
                self.get_yes_no("Supplier quote available?")
            )

        return request

    def choose_budget_club(self, club_names: list[str]) -> str:
        # Choose a club whose annual budget should be displayed.
        return self.select_club(club_names)

    def get_year(self) -> int:
        # Get a four-digit funding year.
        while True:
            year = input("Funding year (e.g. 2026): ").strip()

            if year.isdigit() and len(year) == 4:
                return int(year)

            print("Enter a valid four-digit year.")

    def show_message(self, message: str) -> None:
        # Display a normal message or warning.
        print(message)

    def show_budget(self, budget_info: BudgetInfo, club_name: str, year: int) -> None:
        # Display one club's annual budget position.
        print(f"\n=== {club_name} - {year} BUDGET ===")
        print(f"Annual budget: ${budget_info['annual_budget']:.2f}")
        print(f"Used/committed: ${budget_info['used_budget']:.2f}")
        print(f"Remaining: ${budget_info['remaining_budget']:.2f}")

    def show_result(self, record: FundingRecord) -> None:
        # Display the final funding assessment.
        assessment = record.assessment

        if not assessment:
            print("\nThis request has no completed assessment.")
            return

        ai_failed = record.processing_status == FundingRecord.AI_FAILED

        print("\n=== FUNDING ASSESSMENT ===")
        print(f"Request ID: {record.request_id}")
        print(f"Club: {record.club_name}")
        print(f"Event: {record.request.event_title}")
        print(f"Funding year: {assessment.funding_year}")

        # Make AI failures obvious without losing the parsed/calculated values.
        if ai_failed:
            print("\nAI status: UNAVAILABLE")
            print("AI-dependent categories were not classified. This request requires manual review.")

        print("\nAnnual budget:")
        print(f"Allocated: ${assessment.annual_budget:.2f}")
        print(f"Previously committed: ${assessment.used_budget_before:.2f}")
        print(f"Available before request: ${assessment.remaining_budget_before:.2f}")

        print("\nCurrent request:")
        print(f"Requested: ${assessment.total_requested:.2f}")

        if ai_failed:
            print(f"Provisional eligible amount: ${assessment.estimated_eligible_amount:.2f}")
        else:
            print(f"Estimated eligible: ${assessment.estimated_eligible_amount:.2f}")

        print(f"Status: {assessment.status}")

        if record.budget_committed:
            print(f"Budget deducted/reserved: ${record.budget_amount:.2f}")
            print(f"Budget remaining: ${assessment.remaining_budget_after:.2f}")
        else:
            print("Budget deducted/reserved: $0.00")
            print(f"Budget remaining: ${assessment.remaining_budget_before:.2f}")

        print("\nChecks:")

        for check in assessment.checks:
            print(f"- {check.result}: {check.message}")

        if assessment.issues:
            print("\nIssues:")

            for issue in assessment.issues:
                print(f"- {issue}")

        print("\nThis is a pre-screening result, not final funding approval.")

    def show_requests(self, records: list[FundingRecord], title: str = "Requests") -> None:
        # Display a short list of saved requests.
        print(f"\n=== {title} ===")

        if not records:
            print("No requests found.")
            return

        for record in records:
            assessment = record.assessment
            status = assessment.status if assessment else (record.processing_status or "UNKNOWN")
            total = assessment.total_requested if assessment else 0

            print(
                f"{record.request_id} | "
                f"{record.club_name} | "
                f"{record.funding_year if record.funding_year is not None else '-'} | "
                f"${total:.2f} | "
                f"{status} | "
                f"{record.processing_status}"
            )

    def show_summary(self, summary: JsonDict) -> None:
        # Display summary statistics.
        print("\n=== SUMMARY ===")
        print(f"Total requests: {summary['total_requests']}")
        print(f"Ready for review: {summary['ready_for_review']}")
        print(f"Revision required: {summary['revision_required']}")
        print(f"Manual review: {summary['manual_review']}")
        print(f"AI failed: {summary['ai_failed']}")
        print(f"Total requested: ${summary['total_requested']:.2f}")
        print(f"Estimated eligible: ${summary['estimated_eligible']:.2f}")
        print(f"Budget committed: ${summary['budget_committed']:.2f}")

    def show_policy(self, policy: Policy) -> None:
        # Display the current funding policy.
        print("\n=== CURRENT FUNDING POLICY ===")
        print(f"Max request amount: ${policy.max_request_amount:.2f}")
        print(f"Minimum lead days: {policy.minimum_lead_days}")
        print(f"Food limit per person: ${policy.food_per_person_limit:.2f}")
        print(f"Max prize amount: ${policy.max_prize_amount:.2f}")
        print(f"Equipment quote threshold: ${policy.equipment_quote_threshold:.2f}")
        print(f"Ineligible categories: {', '.join(policy.ineligible_categories) or 'None'}")
        print("Rules:")
        for rule_id, label in RULE_NAMES.items():
            state = "ON" if policy.is_rule_enabled(rule_id) else "OFF"
            print(f"  [{state:3}] {rule_id} - {label}")

    def get_policy_changes(self, policy: Policy) -> JsonDict:
        # Ask for new policy values. Pressing Enter keeps the current value.
        self.show_policy(policy)
        print("\nEnter a new value, or press Enter to keep the current one.")
        changes: JsonDict = {}

        money_fields = [
            ("max_request_amount", "Max request amount ($): "),
            ("food_per_person_limit", "Food limit per person ($): "),
            ("max_prize_amount", "Max prize amount ($): "),
            ("equipment_quote_threshold", "Equipment quote threshold ($): "),
        ]

        for field, prompt in money_fields:
            value = self._get_optional_money(prompt)
            if value is not None:
                changes[field] = value

        lead_days = self._get_optional_whole_number("Minimum lead days: ")
        if lead_days is not None:
            changes["minimum_lead_days"] = lead_days

        print(f"Categories: {', '.join(sorted(VALID_CATEGORIES))}")
        categories = input("Ineligible categories (comma-separated, '-' for none): ").strip()
        if categories == "-":
            changes["ineligible_categories"] = []
        elif categories:
            changes["ineligible_categories"] = [item.strip().lower() for item in categories.split(",") if item.strip()]

        switchable = [rule_id for rule_id in RULE_NAMES if rule_id not in LOCKED_RULES]
        print(f"Rules that can be turned off: {', '.join(switchable)}")
        disabled = input("Rules to turn OFF (comma-separated, '-' to turn all on): ").strip()
        if disabled == "-":
            changes["disabled_rules"] = []
        elif disabled:
            changes["disabled_rules"] = [item.strip().lower() for item in disabled.split(",") if item.strip()]

        return changes

    def _get_optional_money(self, prompt: str) -> float | None:
        while True:
            value = input(prompt).strip()
            if not value:
                return None
            try:
                amount = float(value)
                if amount >= 0:
                    return round(amount, 2)
            except ValueError:
                pass
            print("Enter a valid amount, e.g. 250 or 250.50.")

    def _get_optional_whole_number(self, prompt: str) -> int | None:
        while True:
            value = input(prompt).strip()
            if not value:
                return None
            if value.isdigit():
                return int(value)
            print("Enter a whole number of 0 or more.")
