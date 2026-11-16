from __future__ import annotations

import math
from datetime import date
from werkzeug.datastructures import MultiDict

from models import FundingRequest, JsonDict
from .gui_config import MAX_EXPENSES


class RequestForm:
    """Reads the new-request web form and applies the same input rules as the CLI."""

    def __init__(self, form: MultiDict, club_names: list[str], fixed_club: str | None = None) -> None:
        self._form = form
        self._club_names = club_names
        # Students can only submit for the club they logged in with.
        self._fixed_club = fixed_club
        self.errors: list[str] = []

    def values(self) -> JsonDict:
        """Entered values, used to refill the form after an error."""
        rows = []
        for number in range(1, MAX_EXPENSES + 1):
            if f"description_{number}" not in self._form:
                break
            rows.append({
                "description": self._form.get(f"description_{number}", ""),
                "amount": self._form.get(f"amount_{number}", ""),
                "quote": self._form.get(f"quote_{number}") == "yes",
            })

        fields = ["club_name", "event_title", "event_description", "event_date",
                  "submission_date", "expected_participants"]
        values = {field: self._form.get(field, "").strip() for field in fields}
        if self._fixed_club:
            values["club_name"] = self._fixed_club
        values["expenses"] = rows or [{"description": "", "amount": "", "quote": False}]
        return values

    def to_request(self, request_id: str) -> FundingRequest | None:
        """Return a FundingRequest, or None if any input is invalid (see self.errors)."""
        values = self.values()

        if values["club_name"] not in self._club_names:
            self.errors.append("Select a registered club.")

        for field, label in [("event_title", "Event title"), ("event_description", "Event description")]:
            if not values[field]:
                self.errors.append(f"{label} cannot be empty.")

        for field, label in [("event_date", "Event date"), ("submission_date", "Submission date")]:
            if not self._is_date(values[field]):
                self.errors.append(f"{label} must be a valid date (YYYY-MM-DD).")

        participants = values["expected_participants"]
        if not (participants.isdigit() and int(participants) > 0):
            self.errors.append("Expected participants must be a whole number greater than 0.")

        expenses: list[tuple[str, float, bool]] = []
        for number, row in enumerate(values["expenses"], start=1):
            amount = self._to_money(row["amount"])
            if not row["description"].strip():
                self.errors.append(f"Expense {number}: description cannot be empty.")
            if amount is None:
                self.errors.append(f"Expense {number}: enter a valid amount, e.g. 250 or 250.50.")
            else:
                expenses.append((row["description"].strip(), amount, row["quote"]))

        if self.errors:
            return None

        funding_request = FundingRequest(request_id, values["club_name"], values["event_title"],
                                         values["event_description"], values["event_date"],
                                         values["submission_date"], int(participants))
        for description, amount, quote in expenses:
            funding_request.add_expense(description, amount, quote)
        return funding_request

    @staticmethod
    def _is_date(value: str) -> bool:
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _to_money(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return None
        return round(amount, 2) if math.isfinite(amount) and amount >= 0 else None
