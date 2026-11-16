from models import Assessment, Check
from logic_manager.rule_context import RuleContext
from logic_manager.business_rule import BusinessRule


#rule 1: maximum amount allowed for one request
class RequestLimitRule(BusinessRule):
    rule_id = "request_limit"

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
