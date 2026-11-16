from __future__ import annotations

from werkzeug.datastructures import MultiDict

from models import JsonDict, LOCKED_RULES, Policy, RULE_NAMES


class PolicyForm:
    """Reads the admin policy form. Range checks are done by the Policy class."""

    def __init__(self, form: MultiDict) -> None:
        self._form = form
        self.errors: list[str] = []

    def to_changes(self) -> JsonDict | None:
        changes: JsonDict = {}

        for field in Policy.MONEY_FIELDS:
            try:
                changes[field] = float(self._form.get(field) or "")
            except ValueError:
                self.errors.append(f"{self.label(field)} must be a number.")

        lead_days = (self._form.get("minimum_lead_days") or "").strip()
        if lead_days.isdigit():
            changes["minimum_lead_days"] = int(lead_days)
        else:
            self.errors.append("Minimum lead days must be a whole number of 0 or more.")

        changes["ineligible_categories"] = self._form.getlist("ineligible_categories")

        # Rules are shown as "on" checkboxes; an unticked rule is turned off.
        if self._form.get("rules_form") == "1":
            enabled = self._form.getlist("enabled_rules")
            changes["disabled_rules"] = [rule_id for rule_id in RULE_NAMES
                                         if rule_id not in enabled and rule_id not in LOCKED_RULES]
        return None if self.errors else changes

    @staticmethod
    def label(field: str) -> str:
        return field.replace("_", " ").capitalize()
