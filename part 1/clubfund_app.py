from __future__ import annotations

import hmac
import os

from ai_manager import AIClassifier, AIManager, OpenAIClassifier
from data_manager import DATA_DIR, DataManager
from logic_manager import LogicManager
from models import FundingRecord, FundingRequest, JsonDict

# Admin password. Change it with the CLUBFUND_ADMIN_PASSWORD environment variable.
DEFAULT_ADMIN_PASSWORD = "1234"


class ClubFundApp:
    """Connects the four managers into the ClubFund processing pipeline.

    Both the command-line menu and the GUI use this class, so the
    pipeline is written once.
    """

    def __init__(self, data_manager: DataManager, ai_manager: AIManager, logic_manager: LogicManager) -> None:
        self._data_manager = data_manager
        self._ai_manager = ai_manager
        self._logic_manager = logic_manager

    @classmethod
    def create(cls, data_dir: str = DATA_DIR, classifier: AIClassifier | None = None) -> tuple[ClubFundApp | None, str | None, str | None]:
        """Load the saved data and build the managers.

        Returns (app, warning, error). app is None if the program cannot start.
        """
        data_manager = DataManager(data_dir)
        # Load records from previous program runs (a problem here is only a warning).
        warning = data_manager.load_requests()
        # Funding rules and club budgets are required.
        error = data_manager.load_policy() or data_manager.load_club_budgets()

        if error:
            return None, warning, error

        ai_manager = AIManager(classifier or OpenAIClassifier())
        logic_manager = LogicManager(data_manager.policy, LogicManager.default_rules())
        return cls(data_manager, ai_manager, logic_manager), warning, None

    @property
    def data_manager(self) -> DataManager:
        return self._data_manager

    def new_request_id(self) -> str:
        # Generate the next ID, such as CF0001 or CF0002.
        return self._data_manager.next_request_id()

    def process_request(self, request: FundingRequest) -> tuple[FundingRecord | None, str | None, str | None]:
        """Send one request through AI, business rules and storage.

        Returns (record, ai_error, save_error).
        """
        # Calculate the club's annual budget from saved history.
        budget_info = self._data_manager.get_budget_info(request.club_name, request.funding_year)
        # Every request passes through the AI. If the API fails, a fallback marks everything unknown.
        ai_result, ai_error = self._ai_manager.analyse_request(request)
        # The request passes through the logic manager even when AI fails.
        assessment = self._logic_manager.assess_request(request, ai_result, budget_info)

        if ai_error:
            processing_status = FundingRecord.AI_FAILED
        else:
            processing_status = FundingRecord.PROCESSED

        record = self._data_manager.make_record(request, ai_result, assessment, processing_status, ai_error)
        saved, save_error = self._data_manager.add_request(record)

        if not saved:
            return None, ai_error, save_error
        return record, ai_error, None

    def check_admin_password(self, password: str) -> bool:
        """Admin log-in check used by both the CLI and the GUI."""
        expected = os.getenv("CLUBFUND_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
        # compare_digest takes the same time for any wrong password.
        return hmac.compare_digest(password.encode(), expected.encode())

    def update_policy(self, changes: JsonDict) -> tuple[bool, str]:
        """Admin feature: change the funding policy used for new requests."""
        return self._data_manager.update_policy(changes)
