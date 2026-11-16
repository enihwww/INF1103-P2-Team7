from abc import abstractmethod

from models import Assessment, Check
from logic_manager.rule_context import RuleContext
from logic_manager.business_rule import BusinessRule


#parent class for rules that limit the total of one category (food and prize)
#the checking steps are written once here, child classes only give the category, limit and messages
class CategoryLimitRule(BusinessRule):

    #each child class sets this (e.g. "food")
    category: str = ""

    #returns the amount over the limit, which is removed from the eligible amount
    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        total = context.category_total(self.category)
        limit = self._limit(context)

        if self._applies(context) and total > limit:
            excess = total - limit
            assessment.add_issue(self._issue_message(excess))
            assessment.add_check(Check.FAIL, self._fail_message(limit))
            return excess

        if total > 0:
            assessment.add_check(Check.PASS, self._pass_message())
        return 0.0

    #whether the limit applies to this request, True by default
    #prize rule changes this to only apply to competitions
    def _applies(self, context: RuleContext) -> bool:
        return True

    #every child class must fill in these 4 methods

    #the limit for this category
    @abstractmethod
    def _limit(self, context: RuleContext) -> float:
        pass

    #message saved in the issues list
    @abstractmethod
    def _issue_message(self, excess: float) -> str:
        pass

    #message for the FAIL check
    @abstractmethod
    def _fail_message(self, limit: float) -> str:
        pass

    #message for the PASS check
    @abstractmethod
    def _pass_message(self) -> str:
        pass
