from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from models import FundingRequest


class AIClassifier(ABC):
    """Interface for anything that can classify a funding request."""

    @abstractmethod
    def classify(self, request: FundingRequest) -> Any:
        """Return the parsed AI result, or raise an exception on failure."""
