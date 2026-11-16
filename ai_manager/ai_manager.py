"""AI Manager main file: holds AIManager and imports every class of the AI Manager."""
from __future__ import annotations

from typing import Any

from models import FundingRequest, JsonDict
from .ai_classifier import AIClassifier
from .ai_config import AI_INSTRUCTIONS, MAX_ATTEMPTS, MODEL, REQUEST_TIMEOUT
from .ai_service_error import AIServiceError
from .fallback_classifier import FallbackClassifier
from .openai_classifier import OpenAIClassifier
from .prompt_builder import PromptBuilder
from .response_validator import ResponseValidator


class AIManager:
    """Sends every request through the AI and returns validated JSON."""

    def __init__(self, classifier: AIClassifier, fallback: AIClassifier | None = None, max_attempts: int = MAX_ATTEMPTS) -> None:
        # Aggregation: classifiers are passed in, so tests can use a stub.
        self._classifier = classifier
        self._fallback = fallback or FallbackClassifier()
        self._max_attempts = max_attempts
        # Composition: the manager owns its validator.
        self._validator = ResponseValidator()

    def validate_result(self, result: Any, request: FundingRequest) -> tuple[bool, str]:
        return self._validator.validate(result, request)

    def analyse_request(self, request: FundingRequest) -> tuple[JsonDict, str | None]:
        last_error = "Unknown AI error."

        for _ in range(self._max_attempts):
            try:
                result = self._classifier.classify(request)
                # Every result is validated here, whichever classifier produced it.
                valid, error = self.validate_result(result, request)

                if valid:
                    return result, None

                last_error = error

            except Exception as error:
                last_error = str(error)

        # The live API was attempted but failed. Return a safe fallback so the rest of the
        # application can still calculate non-AI values and produce a MANUAL_REVIEW outcome.
        fallback_result = self._fallback.classify(request)

        return fallback_result, (f"AI processing failed after {self._max_attempts} attempts: {last_error}")


__all__ = [
    "AIClassifier",
    "AIManager",
    "AIServiceError",
    "AI_INSTRUCTIONS",
    "FallbackClassifier",
    "MAX_ATTEMPTS",
    "MODEL",
    "OpenAIClassifier",
    "PromptBuilder",
    "REQUEST_TIMEOUT",
    "ResponseValidator",
]
