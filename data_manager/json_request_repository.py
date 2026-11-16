from __future__ import annotations

import json
import os

from models import FundingRecord
from .repository import Repository


# Saves and loads request records in requests.json
class JsonRequestRepository(Repository):

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path

    def load(self) -> tuple[list[FundingRecord], str | None]:
        if not os.path.exists(self._file_path):
            return [], None

        try:
            with open(self._file_path, "r", encoding="utf-8") as file:
                records = json.load(file)

            if not isinstance(records, list):
                return [], "requests.json must contain a list."

            return [FundingRecord.from_dict(record) for record in records], None

        except (OSError, json.JSONDecodeError) as error:
            return [], f"Could not load requests: {error}"

        except (AttributeError, TypeError, ValueError) as error:
            return [], f"Could not load requests: a saved record is corrupt ({error})."

    def save(self, records: list[FundingRecord]) -> tuple[bool, str | None]:
        try:
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)

            with open(self._file_path, "w", encoding="utf-8") as file:
                json.dump([record.to_dict() for record in records], file, indent=2)

            return True, None

        except OSError as error:
            return False, f"Could not save requests: {error}"
