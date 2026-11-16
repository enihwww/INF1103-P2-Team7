from __future__ import annotations


class Check:
    """One PASS, FAIL or REVIEW message."""

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    SKIPPED = "SKIPPED"  # rule turned off by an admin; does not affect the status

    def __init__(self, result: str, message: str) -> None:
        self._result = result
        self._message = message

    @property
    def result(self) -> str:
        return self._result

    @property
    def message(self) -> str:
        return self._message

    def to_dict(self) -> dict[str, str]:
        return {"result": self._result, "message": self._message}
