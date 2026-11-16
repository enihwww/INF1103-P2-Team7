from logic_manager.rule_context import RuleContext
from logic_manager.category_limit_rule import CategoryLimitRule


#rule 7: competitions have a prize limit (multi-condition rule using ai output)
class PrizeLimitRule(CategoryLimitRule):
    rule_id = "prize_limit"

    category = "prize"

    #only check prizes if the ai says the event is a competition
    def _applies(self, context: RuleContext) -> bool:
        return context.ai_result["event_type"] == "competition"

    def _limit(self, context: RuleContext) -> float:
        return context.policy.max_prize_amount

    def _issue_message(self, excess: float) -> str:
        return f"Competition prizes exceed the limit by ${excess:.2f}."

    def _fail_message(self, limit: float) -> str:
        return f"Competition prize limit is ${limit:.2f}."

    def _pass_message(self) -> str:
        return "No prize-limit problem."
