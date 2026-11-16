from models import Assessment, Check
from logic_manager.rule_context import RuleContext
from logic_manager.business_rule import BusinessRule


#rule 3: request must be submitted early enough
class LeadTimeRule(BusinessRule):
    rule_id = "lead_time"

    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        minimum_days = context.policy.minimum_lead_days

        if context.lead_days < minimum_days:
            assessment.add_issue(f"Request must be submitted at least {minimum_days} days before the event.")
            assessment.add_check(Check.FAIL, f"Only {context.lead_days} day(s) of lead time.")
        else:
            assessment.add_check(Check.PASS, f"{context.lead_days} day(s) of lead time.")
        return 0.0
