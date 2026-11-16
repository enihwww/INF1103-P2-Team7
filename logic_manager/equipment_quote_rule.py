from models import Assessment, Check
from logic_manager.rule_context import RuleContext
from logic_manager.business_rule import BusinessRule


#rule 8: expensive reusable equipment needs a supplier quote (multi-condition rule)
#placed here because it runs before rules 5 to 7, same order as part 1
class EquipmentQuoteRule(BusinessRule):
    rule_id = "equipment_quote"

    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        quote_limit = context.policy.equipment_quote_threshold

        for expense in context.request.expenses:
            category = context.category_of(expense)

            #all 3 conditions must be true: equipment, over the limit, and no quote
            if category == "reusable_equipment" and expense.amount >= quote_limit and not expense.quote_available:
                assessment.add_issue(f"{expense.expense_id} requires a supplier quote.")
                assessment.add_check(Check.FAIL, f"{expense.expense_id} needs a quote (${quote_limit:.2f} or more).")
        return 0.0
