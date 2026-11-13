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