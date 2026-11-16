from __future__ import annotations

from .constants import JsonDict


class Expense:
    """One expense item inside a funding request."""

    def __init__(self, expense_id: str, description: str, amount: float, quote_available: bool) -> None:
        self._expense_id = expense_id
        self._description = description
        self._amount = round(float(amount), 2)
        self._quote_available = bool(quote_available)

    @property
    def expense_id(self) -> str:
        return self._expense_id

    @property
    def description(self) -> str:
        return self._description

    @property
    def amount(self) -> float:
        return self._amount

    @property
    def quote_available(self) -> bool:
        return self._quote_available

    def to_dict(self) -> JsonDict:
        return {
            "expense_id": self._expense_id,
            "description": self._description,
            "amount": self._amount,
            "quote_available": self._quote_available
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "Expense":
        return cls(data.get("expense_id", ""), data.get("description", ""),
                   data.get("amount", 0), data.get("quote_available", False))
