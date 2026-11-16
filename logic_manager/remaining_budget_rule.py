from models import Assessment, Check
from logic_manager.rule_context import RuleContext
from logic_manager.business_rule import BusinessRule


#rule 2: club must have enough annual budget left
class RemainingBudgetRule(BusinessRule):
    rule_id = "remaining_budget"

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
