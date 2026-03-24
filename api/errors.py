from typing import Any

from fastapi import HTTPException


class StructuredHTTPException(HTTPException):
    """
    A unified HTTP exception that formats its detail payload into a structured JSON
    dictionary, making it predictable and easy for clients to parse.
    """

    def __init__(
        self,
        status_code: int,
        error: str,
        detail: str,
        code: str,
        source: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "error": error,
            "detail": detail,
            "code": code,
        }
        if source:
            payload["source"] = source

        super().__init__(status_code=status_code, detail=payload)
