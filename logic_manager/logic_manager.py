#JsonDict and BudgetInfo are only used in type hints (both are dictionaries)
from models import Assessment, BudgetInfo, Check, FundingRequest, JsonDict, Policy
from logic_manager.rule_context import RuleContext
from logic_manager.business_rule import BusinessRule
from logic_manager.request_limit_rule import RequestLimitRule
from logic_manager.remaining_budget_rule import RemainingBudgetRule
from logic_manager.lead_time_rule import LeadTimeRule
from logic_manager.unclear_information_rule import UnclearInformationRule
from logic_manager.equipment_quote_rule import EquipmentQuoteRule
from logic_manager.ineligible_category_rule import IneligibleCategoryRule
from logic_manager.food_limit_rule import FoodLimitRule
from logic_manager.prize_limit_rule import PrizeLimitRule


#apply all ClubFund business rules to a request that the ai has already classified
class LogicManager:

    def __init__(self, policy: Policy, rules: list[BusinessRule]) -> None:
        #association: the same policy object is shared with data_manager,
        #so when the admin updates the policy, the next request uses it straight away
        self._policy: Policy = policy
        #aggregation: the rule objects are created outside and passed in
        self._rules: list[BusinessRule] = list(rules)

    #make the 8 rules from part 1, in the same order the checks were added
    #static because it does not need any LogicManager data, so the rules can be made before LogicManager
    @staticmethod
    def default_rules() -> list[BusinessRule]:
        return [RequestLimitRule(), RemainingBudgetRule(), LeadTimeRule(),
                UnclearInformationRule(), EquipmentQuoteRule(),
                IneligibleCategoryRule(), FoodLimitRule(), PrizeLimitRule()]

    #run every rule on the request and return the assessment (status, checks, issues, amounts)
    def assess_request(self, request: FundingRequest, ai_result: JsonDict, budget_info: BudgetInfo) -> Assessment:
        context = RuleContext(request, ai_result, self._policy, budget_info)
        remaining_budget = budget_info["remaining_budget"]

        #budget info comes from data_manager
        assessment = Assessment(request.funding_year, budget_info["annual_budget"],
                                budget_info["used_budget"], remaining_budget,
                                context.total_requested, context.lead_days)

        #polymorphism: every rule is called the same way with evaluate()
        #some rules also reduce the eligible amount
        eligible_amount = context.total_requested
        caps: list[float] = [context.total_requested]
        for rule in self._rules:
            #skip a rule if the admin turned it off in the policy
            if not self._policy.is_rule_enabled(rule.rule_id):
                assessment.add_check(Check.SKIPPED, f"{rule.label} rule is turned off by an admin.")
                continue

            eligible_amount = eligible_amount - rule.evaluate(context, assessment)

            #collect the limits from rules that have one (rules 1 and 2)
            limit = rule.cap(context)
            if limit is not None:
                caps.append(limit)

        #eligible amount cannot go above the active limits or below 0
        eligible_amount = min([eligible_amount] + caps)
        eligible_amount = round(max(0, eligible_amount), 2)

        #decide the final status and how much budget to commit
        assessment.finalise(eligible_amount)
        return assessment
