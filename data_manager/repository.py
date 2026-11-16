from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


# Interface for loading and saving one kind of data
class Repository(ABC):

    @abstractmethod
    def load(self) -> tuple[Any, str | None]:
        """Return (data, error_message)."""

    @abstractmethod
    def save(self, data: Any) -> tuple[bool, str | None]:
        """Return (success, error_message)."""
