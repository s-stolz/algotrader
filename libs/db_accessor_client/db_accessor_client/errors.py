"""Custom exceptions for the db_accessor_client package."""

from __future__ import annotations


class DatabaseAccessorClientError(Exception):
    """Represents transport or HTTP failures when calling database-accessor-api."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
