from logic_manager.rule_context import RuleContext
from logic_manager.category_limit_rule import CategoryLimitRule


#rule 6: food must stay under the per-person limit
class FoodLimitRule(CategoryLimitRule):
    rule_id = "food_limit"

    category = "food"

    #food limit = number of people x limit per person
    def _limit(self, context: RuleContext) -> float:
        return context.request.expected_participants * context.policy.food_per_person_limit

    def _issue_message(self, excess: float) -> str:
        return f"Food exceeds the allowed amount by ${excess:.2f}."

    def _fail_message(self, limit: float) -> str:
        return f"Food limit is ${limit:.2f}."

    def _pass_message(self) -> str:
        return "Food spending is within the limit."
