from __future__ import annotations

from .assessment import Assessment
from .constants import JsonDict
from .funding_request import FundingRequest


class FundingRecord:
    """A saved request together with its AI result and assessment."""

    PROCESSED = "PROCESSED"
    AI_FAILED = "AI_FAILED"

    def __init__(self, request: FundingRequest, ai_result: JsonDict | None, assessment: Assessment | None,
                 processing_status: str, processing_error: str | None = None,
                 budget_committed: bool = False, budget_amount: float = 0.0) -> None:
        self._request = request
        self._ai_result = ai_result
        self._assessment = assessment
        self._processing_status = processing_status
        self._processing_error = processing_error
        self._budget_committed = budget_committed
        self._budget_amount = budget_amount

    @property
    def request(self) -> FundingRequest:
        return self._request

    @property
    def request_id(self) -> str:
        return self._request.request_id

    @property
    def club_name(self) -> str:
        return self._request.club_name

    @property
    def funding_year(self) -> int | None:
        return self._request.funding_year

    @property
    def ai_result(self) -> JsonDict | None:
        return self._ai_result

    @property
    def assessment(self) -> Assessment | None:
        return self._assessment

    @property
    def processing_status(self) -> str:
        return self._processing_status

    @property
    def processing_error(self) -> str | None:
        return self._processing_error

    @property
    def budget_committed(self) -> bool:
        return self._budget_committed

    @property
    def budget_amount(self) -> float:
        return self._budget_amount

    def to_dict(self) -> JsonDict:
        record = self._request.to_dict()
        record["ai_result"] = self._ai_result
        record["assessment"] = self._assessment.to_dict() if self._assessment else None
        record["processing_status"] = self._processing_status
        record["processing_error"] = self._processing_error
        record["budget_committed"] = self._budget_committed
        record["budget_amount"] = self._budget_amount
        return record

    @classmethod
    def from_dict(cls, data: JsonDict) -> "FundingRecord":
        assessment_data = data.get("assessment")
        assessment = Assessment.from_dict(assessment_data) if assessment_data else None

        return cls(FundingRequest.from_dict(data), data.get("ai_result"), assessment,
                   data.get("processing_status", ""), data.get("processing_error"),
                   data.get("budget_committed", False), data.get("budget_amount", 0.0))
