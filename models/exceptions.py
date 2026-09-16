"""
Custom exceptions for SignalHire Lead Generation Agent.

This module centralizes all domain-specific exceptions used across CLI, services,
and models. Keep exceptions lightweight and typed, and validate inputs.
"""

from __future__ import annotations

__all__ = [
    "AuthenticationError",
    "BrowserAutomationError",
    "BrowserError",
    "ConfigurationError",
    "DataExtractionError",
    "DataValidationError",
    "FileOperationError",
    "InsufficientCreditsError",
    "NetworkTimeoutError",
    "RateLimitError",
    "RateLimitExceededError",
    "SignalHireAPIError",
    "SignalHireError",
]


def _require_non_empty_message(message: str) -> None:
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")


class SignalHireError(Exception):
    """Base exception for SignalHire agent errors."""

    def __init__(self, message: str, details: str | None = None):
        _require_non_empty_message(message)
        self.message = message
        self.details = details
        super().__init__(self.message)


class SignalHireAPIError(SignalHireError):
    """API-related errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class RateLimitError(SignalHireError):
    """General rate limiting error (API or browser)."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        if retry_after is not None and not isinstance(retry_after, int):
            raise ValueError("retry_after must be an integer number of seconds")
        self.retry_after = retry_after


class RateLimitExceededError(RateLimitError):
    """Explicit rate limit exceeded error variant."""


class InsufficientCreditsError(SignalHireError):
    """Insufficient credits errors."""

    def __init__(
        self, message: str, required_credits: int, available_credits: int
    ) -> None:
        super().__init__(message)
        if not isinstance(required_credits, int) or required_credits < 0:
            raise ValueError("required_credits must be a non-negative integer")
        if not isinstance(available_credits, int) or available_credits < 0:
            raise ValueError("available_credits must be a non-negative integer")
        self.required_credits = required_credits
        self.available_credits = available_credits


class BrowserAutomationError(SignalHireError):
    """Browser automation errors (Playwright/Stagehand layer)."""

    def __init__(self, message: str, screenshot_path: str | None = None) -> None:
        super().__init__(message)
        if screenshot_path is not None and not isinstance(screenshot_path, str):
            raise ValueError("screenshot_path must be a string if provided")
        self.screenshot_path = screenshot_path


class BrowserError(BrowserAutomationError):
    """Alias/general browser error used by newer browser client implementations."""


class NetworkTimeoutError(SignalHireError):
    """Network timeout errors."""

    def __init__(self, message: str, timeout_duration: float | None = None) -> None:
        super().__init__(message)
        if timeout_duration is not None and not isinstance(
            timeout_duration, (int, float)
        ):
            raise ValueError("timeout_duration must be numeric if provided")
        self.timeout_duration = (
            float(timeout_duration) if timeout_duration is not None else None
        )


class AuthenticationError(SignalHireError):
    """Authentication errors (HTTP 401/403 or browser login failures)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        if status_code is not None and not isinstance(status_code, int):
            raise ValueError("status_code must be an integer if provided")
        self.status_code = status_code


class DataValidationError(SignalHireError):
    """Data validation errors."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        field_value: str | None = None,
    ) -> None:
        super().__init__(message)
        if field_name is not None and not isinstance(field_name, str):
            raise ValueError("field_name must be a string if provided")
        if field_value is not None and not isinstance(field_value, str):
            raise ValueError("field_value must be a string if provided")
        self.field_name = field_name
        self.field_value = field_value


class DataExtractionError(SignalHireError):
    """Errors while extracting or parsing data from browser/API responses."""


class ConfigurationError(SignalHireError):
    """Configuration errors."""


class FileOperationError(SignalHireError):
    """File operation errors."""

    def __init__(self, message: str, file_path: str | None = None) -> None:
        super().__init__(message)
        if file_path is not None and not isinstance(file_path, str):
            raise ValueError("file_path must be a string if provided")
        self.file_path = file_path
