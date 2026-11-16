from __future__ import annotations

import json


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
