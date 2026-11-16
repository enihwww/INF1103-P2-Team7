from __future__ import annotations

import json

from models import Policy, PolicyError
from .repository import Repository


# Saves and loads the funding policy in policy.json
class JsonPolicyRepository(Repository):

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path

    def load(self) -> tuple[Policy | None, str | None]:
        try:
            with open(self._file_path, "r", encoding="utf-8") as file:
                return Policy.from_dict(json.load(file)), None

        except FileNotFoundError:
            return None, "policy.json was not found."

        except (OSError, json.JSONDecodeError) as error:
            return None, f"Could not load policy: {error}"

        except PolicyError as error:
            return None, str(error)

    def save(self, policy: Policy) -> tuple[bool, str | None]:
        try:
            with open(self._file_path, "w", encoding="utf-8") as file:
                json.dump(policy.to_dict(), file, indent=2)

            return True, None

        except OSError as error:
            return False, f"Could not save policy: {error}"
