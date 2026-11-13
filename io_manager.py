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

