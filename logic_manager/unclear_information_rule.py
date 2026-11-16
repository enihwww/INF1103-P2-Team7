from models import Assessment, Check
from logic_manager.rule_context import RuleContext
from logic_manager.business_rule import BusinessRule


#rule 4: missing or unclear ai information needs a human to check
class UnclearInformationRule(BusinessRule):
    rule_id = "unclear_information"

    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        ai_result = context.ai_result

        #ai could not tell what kind of event it is
        if ai_result["event_type"] == "unknown":
            assessment.add_issue("Event type could not be classified.")
            assessment.add_check(Check.REVIEW, "Event type needs human review.")

        #ai found details missing from the request
        if ai_result["missing_information"]:
            assessment.add_issue("Missing information: " + ", ".join(ai_result["missing_information"]))
            assessment.add_check(Check.REVIEW, "Some request information is missing.")

        #ai was not sure about an expense, or could not classify it
        for expense in context.request.expenses:
            ai_expense = context.ai_expenses[expense.expense_id]

            if ai_expense["ambiguous"] or ai_expense["category"] == "unknown":
                assessment.add_issue(f"{expense.expense_id} could not be classified clearly.")
                assessment.add_check(Check.REVIEW, f"{expense.expense_id} needs human review.")
        return 0.0
