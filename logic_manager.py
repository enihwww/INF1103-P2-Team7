from models import BudgetInfo, Expense, FundingRequest, JsonDict, Policy

#holds the values every rule needs while one request is being checked
#so each rule does not have to work them out again
class RuleContext:
    def __init__(self, request: FundingRequest, ai_result: JsonDict, policy: Policy, budget_info: BudgetInfo) -> None:
        self.request: FundingRequest = request
        self.ai_result: JsonDict = ai_result
        self.policy: Policy = policy
        self.budget_info: BudgetInfo = budget_info
        self.ai_expenses: dict[str, JsonDict] = self._build_ai_lookup()
        self.total_requested: float = request.total_amount()
        self.lead_days: int = request.lead_days()

    #put the ai results in a dictionary so we can look them up by expense id (E1, E2...)
    def _build_ai_lookup(self) -> dict[str, JsonDict]:
        ai_expenses = {}

        for ai_expense in self.ai_result["expenses"]:
            ai_expenses[ai_expense["expense_id"]] = ai_expense

        #if the ai missed an expense, mark it as unknown so it goes to manual review
        for expense in self.request.expenses:
            if expense.expense_id not in ai_expenses:
                ai_expenses[expense.expense_id] = {"category": "unknown", "ambiguous": True}
        return ai_expenses

    #return the ai category of one expense (e.g. "food")
    def category_of(self, expense: Expense) -> str:
        return self.ai_expenses[expense.expense_id]["category"]

    #add up the amounts of all expenses in one category (e.g. "food")
    def category_total(self, category: str) -> float:
        total = 0.0
        for expense in self.request.expenses:
            if self.category_of(expense) == category:
                total += expense.amount
        return round(total, 2)


