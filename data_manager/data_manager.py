from __future__ import annotations

import os

from models import Assessment, BudgetInfo, FundingRecord, FundingRequest, JsonDict, Policy, PolicyError
from .budget_ledger import BudgetLedger
from .data_config import BASE_DIR, DATA_DIR
from .excel_report_exporter import ExcelReportExporter
from .json_budget_repository import JsonBudgetRepository
from .json_policy_repository import JsonPolicyRepository
from .json_request_repository import JsonRequestRepository
from .repository import Repository

# Single entry point for saving, loading and summarising ClubFund data
class DataManager:

    def __init__(self, data_dir: str = DATA_DIR) -> None:
        self._data_dir = data_dir
        # Composition: the data manager creates and owns its repositories and exporter.
        self._request_repository = JsonRequestRepository(os.path.join(data_dir, "requests.json"))
        self._policy_repository = JsonPolicyRepository(os.path.join(data_dir, "policy.json"))
        self._budget_repository = JsonBudgetRepository(os.path.join(data_dir, "club_budgets.json"))
        self._exporter = ExcelReportExporter()
        self.excel_file = os.path.join(data_dir, "ClubFund_Report.xlsx")

        self._records: list[FundingRecord] = []
        self._policy: Policy | None = None
        self._budgets: dict[str, float] = {}
        self._ledger = BudgetLedger(self._budgets, self._records)

    # Load saved requests from previous program runs
    def load_requests(self) -> str | None:
        records, error = self._request_repository.load()
        self._records[:] = records  # keep the same list object shared with the ledger
        return error

    def load_policy(self) -> str | None:
        self._policy, error = self._policy_repository.load()
        return error

    def load_club_budgets(self) -> str | None:
        budgets, error = self._budget_repository.load()
        self._budgets.clear()
        if budgets:
            self._budgets.update(budgets)
        return error

    @property
    def records(self) -> list[FundingRecord]:
        return list(self._records)

    @property
    def policy(self) -> Policy:
        if self._policy is None:
            raise RuntimeError("The funding policy has not been loaded.")
        return self._policy

    @property
    def budgets(self) -> dict[str, float]:
        return dict(self._budgets)

    # Return club names in alphabetical order
    def get_club_names(self) -> list[str]:
        return sorted(self._budgets.keys())

    # Records of one club only (what a student is allowed to see)
    def records_for_club(self, club_name: str) -> list[FundingRecord]:
        return [record for record in self._records if record.club_name == club_name]

    def find_record(self, request_id: str) -> FundingRecord | None:
        for record in self._records:
            if record.request_id == request_id:
                return record
        return None

    # Generate CF0001, CF0002, CF0003, etc...
    def next_request_id(self) -> str:
        highest_number = 0

        for record in self._records:
            request_id = record.request_id or ""

            if request_id.startswith("CF") and request_id[2:].isdigit():
                highest_number = max(highest_number, int(request_id[2:]))

        return f"CF{highest_number + 1:04d}"

    def get_budget_info(self, club_name: str, year: int | None) -> BudgetInfo:
        return self._ledger.get_budget_info(club_name, year)

    # Combine input, AI output and assessment for saving
    def make_record(self, request: FundingRequest, ai_result: JsonDict | None, assessment: Assessment | None, processing_status: str, error: str | None = None) -> FundingRecord:
        # A failed API request produces MANUAL_REVIEW, so it will never reserve annual budget.
        if (
            assessment
            and assessment.status == Assessment.READY
            and processing_status == FundingRecord.PROCESSED
        ):
            return FundingRecord(request, ai_result, assessment, processing_status, error,
                                 True, assessment.budget_to_commit)

        return FundingRecord(request, ai_result, assessment, processing_status, error, False, 0.0)

    def add_request(self, record: FundingRecord) -> tuple[bool, str | None]:
        """Add one record and save the updated list."""
        self._records.append(record)
        success, error = self._request_repository.save(self._records)

        if not success:
            self._records.pop()

        return success, error

    # ADMIN Feature! Validate, save and apply new policy values
    def update_policy(self, changes: JsonDict) -> tuple[bool, str]:
        """The live policy only changes after the file is saved, so the
        program and policy.json never disagree."""
        try:
            candidate = Policy.from_dict(self.policy.to_dict())
            candidate.update(changes)
        except PolicyError as error:
            return False, str(error)

        saved, save_error = self._policy_repository.save(candidate)
        if not saved:
            return False, save_error or "Could not save policy."

        # Update the shared object so the logic manager uses the new values straight away.
        self.policy.update(candidate.to_dict())
        return True, "Funding policy updated."

    # Calculate statistics for the summary menu
    def build_summary(self, records: list[FundingRecord] | None = None) -> JsonDict:
        if records is None:
            records = self._records

        summary: JsonDict = {
            "total_requests": len(records),
            "ready_for_review": 0,
            "revision_required": 0,
            "manual_review": 0,
            "ai_failed": 0,
            "total_requested": 0.0,
            "estimated_eligible": 0.0,
            "budget_committed": 0.0,
        }

        for record in records:
            assessment = record.assessment
            status = assessment.status if assessment else None

            if status == Assessment.READY:
                summary["ready_for_review"] += 1

            elif status == Assessment.REVISION:
                summary["revision_required"] += 1

            elif status == Assessment.MANUAL:
                summary["manual_review"] += 1

            if record.processing_status == FundingRecord.AI_FAILED:
                summary["ai_failed"] += 1

            # AI-failed records still have an assessment, so their deterministic values are included here.
            if assessment:
                summary["total_requested"] += assessment.total_requested
                summary["estimated_eligible"] += assessment.estimated_eligible_amount

            summary["budget_committed"] += record.budget_amount

        for field in ["total_requested", "estimated_eligible", "budget_committed"]:
            summary[field] = round(summary[field], 2)

        return summary

    # Create an Excel report from the JSON records
    def export_to_excel(self, records: list[FundingRecord] | None = None, file_path: str | None = None) -> tuple[bool, str]:
        if records is None:
            records = self._records
        if file_path is None:
            file_path = self.excel_file

        ledger = BudgetLedger(self._budgets, records)
        summary = self.build_summary(records)
        return self._exporter.export(file_path, records, self._budgets, ledger, summary)


__all__ = [
    "BASE_DIR",
    "BudgetLedger",
    "DATA_DIR",
    "DataManager",
    "ExcelReportExporter",
    "JsonBudgetRepository",
    "JsonPolicyRepository",
    "JsonRequestRepository",
    "Repository",
]
