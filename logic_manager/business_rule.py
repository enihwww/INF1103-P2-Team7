from abc import ABC, abstractmethod

from models import RULE_NAMES, Assessment
from logic_manager.rule_context import RuleContext


#abstract class for one ClubFund business rule
#every rule must have evaluate(), so LogicManager can use all rules the same way
class BusinessRule(ABC):

    #each child class sets its own id (e.g. "food_limit"), used to turn rules on or off
    rule_id: str = ""

    #check the request and add PASS, FAIL or REVIEW messages to the assessment
    #returns the amount to remove from the eligible amount (0 if the rule only checks)
    @abstractmethod
    def evaluate(self, context: RuleContext, assessment: Assessment) -> float:
        pass

    #the most this rule allows to be funded, None means no limit
    #only rules 1 and 2 change this
    def cap(self, context: RuleContext) -> float | None:
        return None

    #the rule name shown to the user (e.g. "Food per-person limit")
    @property
    def label(self) -> str:
        return RULE_NAMES.get(self.rule_id, type(self).__name__)
