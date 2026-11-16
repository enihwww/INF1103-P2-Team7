from __future__ import annotations

import json
from typing import Any
try:
    from openai import OpenAI
except ImportError:
    # Handled in OpenAIClassifier.classify() so the rest of the app still runs.
    OpenAI = None


from models import FundingRequest
from .ai_classifier import AIClassifier
from .ai_config import AI_INSTRUCTIONS, MODEL, REQUEST_TIMEOUT
from .ai_service_error import AIServiceError
from .prompt_builder import PromptBuilder


class OpenAIClassifier(AIClassifier):
    """Live classifier that calls the OpenAI API."""

    def __init__(self, model: str = MODEL, timeout: float = REQUEST_TIMEOUT) -> None:
        self._model = model
        self._timeout = timeout
        # Composition: the classifier creates and owns its prompt builder.
        self._prompt_builder = PromptBuilder()

    def classify(self, request: FundingRequest) -> Any:
        if OpenAI is None:
            raise AIServiceError("The openai package is not installed.")

        client = OpenAI(timeout=self._timeout)
        response = client.responses.create(model=self._model, instructions=AI_INSTRUCTIONS,
                                           input=self._prompt_builder.build(request))
        # A malformed reply raises json.JSONDecodeError, handled by AIManager.
        return json.loads(response.output_text)
