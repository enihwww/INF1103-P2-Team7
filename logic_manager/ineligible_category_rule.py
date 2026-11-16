from models import Assessment, Check
from logic_manager.rule_context import RuleContext
from logic_manager.business_rule import BusinessRule


#rule 5: some categories cannot be funded
#returns the amount to remove from the eligible amount
class IneligibleCategoryRule(BusinessRule):
    rule_id = "ineligible_category"

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
