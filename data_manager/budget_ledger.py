from __future__ import annotations

from models import BudgetInfo, FundingRecord

# Works out used and remaining budget from the saved records
class BudgetLedger:

    def __init__(self, budgets: dict[str, float], records: list[FundingRecord]) -> None:
        # Aggregation: the records list belongs to the DataManager and is shared here.
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
