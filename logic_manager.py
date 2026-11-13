from models import BudgetInfo, Expense, FundingRequest, JsonDict, Policy, Assessment, RULE_NAMES, Check
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
    #each child class sets its own id, used to turn rules on or off
    rule_id: str = ""

    #check the request and add PASS, FAIL or REVIEW messages to the assessment
    @abstractmethod
    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        pass

    #for rules 1 and 2
    def cap(self, context: RuleContext) -> float | None:
        return None

    @property
    def label(self) -> str:
        return RULE_NAMES.get(self.rule_id, type(self).__name__)

#rule 1: maximum amount allowed for one request
class RequestLimitRule(BusinessRule):
    rule_id: str = "request_limit"

    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        max_request = context.policy.max_request_amount
        if context.total_requested > max_request:
            assessment.add_issue(f"Total request exceeds the ${max_request:.2f} single-request limit.")
            assessment.add_check(Check.FAIL, "Request is over the single-request limit.")
        else:
            assessment.add_check(Check.PASS, "Request is within the single-request limit.")
        return 0.0

    #eligible amount can never be more than the single-request limit
    def cap(self, context: RuleContext) -> float | None:
        return context.policy.max_request_amount

#rule 2: club must have enough annual budget left
class RemainingBudgetRule(BusinessRule):
    rule_id: str = "remaining_budget"

    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        remaining_budget = context.budget_info["remaining_budget"]
        annual_budget = context.budget_info["annual_budget"]

        if context.total_requested > remaining_budget:
            shortfall = context.total_requested - remaining_budget
            assessment.add_issue(f"Request exceeds the remaining annual budget by ${shortfall:.2f}.")
            assessment.add_check(Check.FAIL, f"Only ${remaining_budget:.2f} left from the ${annual_budget:.2f} budget.")
        else:
            assessment.add_check(Check.PASS, f"${remaining_budget:.2f} is available before this request.")
        return 0.0

    #eligible amount can never be more than what the club has left
    def cap(self, context: RuleContext) -> float | None:
        return context.budget_info["remaining_budget"]

#rule 3: request must be submitted early enough
class LeadTimeRule(BusinessRule):
    rule_id: str = "lead_time"

    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        minimum_days = context.policy.minimum_lead_days

        if context.lead_days < minimum_days:
            assessment.add_issue(f"Request must be submitted at least {minimum_days} days before the event.")
            assessment.add_check(Check.FAIL, f"Only {context.lead_days} day(s) of lead time.")
        else:
            assessment.add_check(Check.PASS, f"{context.lead_days} day(s) of lead time.")
        return 0.0

#rule 4: missing or unclear ai information needs a human to check
class UnclearInformationRule(BusinessRule):
    rule_id: str = "unclear_information"
    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        ai_result = context.ai_result

        if ai_result["event_type"] == "unknown":
            assessment.add_issue("Event type could not be classified.")
            assessment.add_check(Check.REVIEW, "Event type needs human review.")

        if ai_result["missing_information"]:
            assessment.add_issue("Missing information: " + ", ".join(ai_result["missing_information"]))
            assessment.add_check(Check.REVIEW, "Some request information is missing.")

        #when ai could not classify an expense clearly
        for expense in context.request.expenses:
            ai_expense = context.ai_expenses[expense.expense_id]

            if ai_expense["ambiguous"] or ai_expense["category"] == "unknown":
                assessment.add_issue(f"{expense.expense_id} could not be classified clearly.")
                assessment.add_check(Check.REVIEW, f"{expense.expense_id} needs human review.")
        return 0.0

#rule 8: expensive reusable equipment needs a supplier quote (multi-condition rule)
class EquipmentQuoteRule(BusinessRule):
    rule_id: str = "equipment_quote"

    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        quote_limit = context.policy.equipment_quote_threshold

        for expense in context.request.expenses:
            category = context.category_of(expense)

            #all 3 conditions must be true: equipment, over the limit and no quote
            if category == "reusable_equipment" and expense.amount >= quote_limit and not expense.quote_available:
                assessment.add_issue(f"{expense.expense_id} requires a supplier quote.")
                assessment.add_check(Check.FAIL, f"{expense.expense_id} needs a quote (${quote_limit:.2f} or more).")
        return 0.0

#rule 5: some categories cannot be funded
#returns the amount to remove from the eligible amount
class IneligibleCategoryRule(BusinessRule):
    rule_id: str = "ineligible_category"

    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        ineligible_categories = context.policy.ineligible_categories
        amount_removed = 0.0

        for expense in context.request.expenses:
            category = context.category_of(expense)

            if category in ineligible_categories:
                amount_removed = amount_removed + expense.amount
                assessment.add_issue(f"{expense.expense_id} ({category}) is not fundable.")
                assessment.add_check(Check.FAIL, f"{expense.expense_id} ({category}) is not fundable.")
        return amount_removed
