from models import BudgetInfo, Expense, FundingRequest, JsonDict, Policy, Assessment, RULE_NAMES
from abc import ABC, abstractmethod

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

#abstract class for one business rule
class BusinessRule(ABC):
    #each child class sets its own id (e.g. "food_limit"), used to turn rules on or off
    rule_id: str = ""

    #check the request and add PASS, FAIL or REVIEW messages to the assessment
    @abstractmethod
    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        pass

    def cap(self, context: RuleContext) -> float | None:
        return None

    #the rule name shown to the user
    @property
    def label(self) -> str:
        return RULE_NAMES.get(self.rule_id, type(self).__name__)

