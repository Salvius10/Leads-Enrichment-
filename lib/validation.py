"""
Validation utilities for SignalHire Agent.

This module provides comprehensive validation functions used across
the application for data validation, input sanitization, and security.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import structlog

from models.exceptions import DataValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

# Common regex patterns
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
LINKEDIN_PROFILE_PATTERN = re.compile(r'^https?://(?:www\.)?linkedin\.com/in/[\w-]+/?$')
LINKEDIN_COMPANY_PATTERN = re.compile(
    r'^https?://(?:www\.)?linkedin\.com/company/[\w-]+/?$'
)
PHONE_PATTERN = re.compile(r'^\+?[1-9][\d\s\-()]{7,15}$')
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE
)
SIGNALHIRE_UID_PATTERN = re.compile(r'^[0-9a-f]{32}$', re.IGNORECASE)


class ValidationResult:
    """Result of a validation operation."""

    def __init__(
        self,
        is_valid: bool,
        error_message: str | None = None,
        cleaned_value: Any = None,
    ):
        self.is_valid = is_valid
        self.error_message = error_message
        self.cleaned_value = cleaned_value

    def __bool__(self) -> bool:
        return self.is_valid

    def raise_if_invalid(self, field_name: str | None = None) -> Any:
        """Raise DataValidationError if validation failed."""
        if not self.is_valid:
            raise DataValidationError(
                self.error_message or "Validation failed",
                field_name=field_name,
                field_value=(
                    str(self.cleaned_value) if self.cleaned_value is not None else None
                ),
            )
        return self.cleaned_value


def validate_email(email: str | None) -> ValidationResult:
    """
    Validate email address format.
    Args:
        email: Email to validate
    Returns:
        ValidationResult with cleaned email
    """
    if not email:
        return ValidationResult(False, "Email is required")

    if not isinstance(email, str):
        return ValidationResult(False, "Email must be a string")

    cleaned_email = email.strip().lower()

    if not cleaned_email:
        return ValidationResult(False, "Email cannot be empty")

    if len(cleaned_email) > 254:  # RFC 5321 limit
        return ValidationResult(False, "Email is too long (max 254 characters)")

    if not EMAIL_PATTERN.match(cleaned_email):
        return ValidationResult(False, "Invalid email format")

    return ValidationResult(True, cleaned_value=cleaned_email)


def validate_linkedin_profile(url: str | None) -> ValidationResult:
    """
    Validate LinkedIn profile URL.
    Args:
        url: LinkedIn URL to validate
    Returns:
        ValidationResult with cleaned URL
    """
    if not url:
        return ValidationResult(False, "LinkedIn URL is required")

    if not isinstance(url, str):
        return ValidationResult(False, "LinkedIn URL must be a string")

    cleaned_url = url.strip()

    # Add https:// if missing
    if not cleaned_url.startswith(('http://', 'https://')):
        cleaned_url = 'https://' + cleaned_url

    if not LINKEDIN_PROFILE_PATTERN.match(cleaned_url):
        return ValidationResult(False, "Invalid LinkedIn profile URL format")

    return ValidationResult(True, cleaned_value=cleaned_url)


def validate_linkedin_company(url: str | None) -> ValidationResult:
    """
    Validate LinkedIn company URL.
    Args:
        url: LinkedIn company URL to validate
    Returns:
        ValidationResult with cleaned URL
    """
    if not url:
        return ValidationResult(False, "LinkedIn company URL is required")

    if not isinstance(url, str):
        return ValidationResult(False, "LinkedIn company URL must be a string")

    cleaned_url = url.strip()

    # Add https:// if missing
    if not cleaned_url.startswith(('http://', 'https://')):
        cleaned_url = 'https://' + cleaned_url

    if not LINKEDIN_COMPANY_PATTERN.match(cleaned_url):
        return ValidationResult(False, "Invalid LinkedIn company URL format")

    return ValidationResult(True, cleaned_value=cleaned_url)


def validate_phone(phone: str | None) -> ValidationResult:
    """
    Validate phone number format.
    Args:
        phone: Phone number to validate
    Returns:
        ValidationResult with cleaned phone number
    """
    if not phone:
        return ValidationResult(False, "Phone number is required")

    if not isinstance(phone, str):
        return ValidationResult(False, "Phone number must be a string")

    # Clean phone number but preserve original for pattern matching
    original = phone.strip()
    cleaned = re.sub(r'[^\d\+]', '', original)

    if not cleaned:
        return ValidationResult(False, "Phone number cannot be empty")

    if len(cleaned) < 7:
        return ValidationResult(False, "Phone number is too short")

    if len(cleaned) > 15:  # ITU-T E.164 standard
        return ValidationResult(False, "Phone number is too long")

    if not PHONE_PATTERN.match(original):
        return ValidationResult(False, "Invalid phone number format")

    return ValidationResult(True, cleaned_value=cleaned)


def validate_url(url: str | None, require_https: bool = False) -> ValidationResult:
    """
    Validate URL format.
    Args:
        url: URL to validate
        require_https: Require HTTPS protocol
    Returns:
        ValidationResult with cleaned URL
    """
    if not url:
        return ValidationResult(False, "URL is required")

    if not isinstance(url, str):
        return ValidationResult(False, "URL must be a string")

    cleaned_url = url.strip()

    # Add https:// if missing
    if not cleaned_url.startswith(('http://', 'https://')):
        cleaned_url = 'https://' + cleaned_url

    try:
        parsed = urlparse(cleaned_url)
    except ValueError as e:
        return ValidationResult(False, f"Invalid URL format: {e}")

    if not parsed.scheme or not parsed.netloc:
        return ValidationResult(False, "Invalid URL format")

    if require_https and parsed.scheme != 'https':
        return ValidationResult(False, "HTTPS is required")

    return ValidationResult(True, cleaned_value=cleaned_url)


def validate_signalhire_uid(uid: str | None) -> ValidationResult:
    """
    Validate SignalHire UID format.
    Args:
        uid: UID to validate
    Returns:
        ValidationResult with cleaned UID
    """
    if not uid:
        return ValidationResult(False, "SignalHire UID is required")

    if not isinstance(uid, str):
        return ValidationResult(False, "SignalHire UID must be a string")

    cleaned_uid = uid.strip().lower()

    if not SIGNALHIRE_UID_PATTERN.match(cleaned_uid):
        return ValidationResult(
            False, "Invalid SignalHire UID format (must be 32 hex characters)"
        )

    return ValidationResult(True, cleaned_value=cleaned_uid)


def validate_uuid(uuid_str: str | None) -> ValidationResult:
    """
    Validate UUID format.
    Args:
        uuid_str: UUID string to validate
    Returns:
        ValidationResult with cleaned UUID
    """
    if not uuid_str:
        return ValidationResult(False, "UUID is required")

    if not isinstance(uuid_str, str):
        return ValidationResult(False, "UUID must be a string")

    cleaned_uuid = uuid_str.strip().lower()

    if not UUID_PATTERN.match(cleaned_uuid):
        return ValidationResult(False, "Invalid UUID format")

    return ValidationResult(True, cleaned_value=cleaned_uuid)


def validate_string_length(
    text: str | None,
    min_length: int = 0,
    max_length: int | None = None,
    field_name: str = "Text",
) -> ValidationResult:
    """
    Validate string length constraints.
    Args:
        text: String to validate
        min_length: Minimum length
        max_length: Maximum length
        field_name: Field name for error messages
    Returns:
        ValidationResult with cleaned string
    """
    if text is None:
        if min_length > 0:
            return ValidationResult(False, f"{field_name} is required")
        return ValidationResult(True, cleaned_value="")

    if not isinstance(text, str):
        return ValidationResult(False, f"{field_name} must be a string")

    cleaned_text = text.strip()
    length = len(cleaned_text)

    if length < min_length:
        return ValidationResult(
            False, f"{field_name} must be at least {min_length} characters"
        )

    if max_length is not None and length > max_length:
        return ValidationResult(
            False, f"{field_name} must be at most {max_length} characters"
        )

    return ValidationResult(True, cleaned_value=cleaned_text)


def validate_choice(
    value: Any, valid_choices: list[Any], field_name: str = "Value"
) -> ValidationResult:
    """
    Validate that value is in list of valid choices.
    Args:
        value: Value to validate
        valid_choices: List of valid choices
        field_name: Field name for error messages
    Returns:
        ValidationResult with cleaned value
    """
    if value not in valid_choices:
        choices_str = ", ".join(str(choice) for choice in valid_choices)
        return ValidationResult(False, f"{field_name} must be one of: {choices_str}")

    return ValidationResult(True, cleaned_value=value)


def validate_integer_range(
    value: int | str | None,
    min_value: int | None = None,
    max_value: int | None = None,
    field_name: str = "Value",
) -> ValidationResult:
    """
    Validate integer within range.
    Args:
        value: Value to validate
        min_value: Minimum value
        max_value: Maximum value
        field_name: Field name for error messages
    Returns:
        ValidationResult with cleaned integer
    """
    if value is None:
        return ValidationResult(False, f"{field_name} is required")

    try:
        int_value = int(value)
    except (ValueError, TypeError):
        return ValidationResult(False, f"{field_name} must be an integer")

    if min_value is not None and int_value < min_value:
        return ValidationResult(False, f"{field_name} must be at least {min_value}")

    if max_value is not None and int_value > max_value:
        return ValidationResult(False, f"{field_name} must be at most {max_value}")

    return ValidationResult(True, cleaned_value=int_value)


def validate_file_path(
    path: str | Path | None,
    must_exist: bool = False,
    allowed_extensions: list[str] | None = None,
    field_name: str = "File path",
) -> ValidationResult:
    """
    Validate file path.
    Args:
        path: Path to validate
        must_exist: Whether file must exist
        allowed_extensions: List of allowed file extensions
        field_name: Field name for error messages
    Returns:
        ValidationResult with cleaned Path object
    """
    if not path:
        return ValidationResult(False, f"{field_name} is required")

    try:
        path_obj = Path(path)
    except TypeError as e:
        return ValidationResult(False, f"Invalid {field_name.lower()}: {e}")

    if must_exist and not path_obj.exists():
        return ValidationResult(False, f"{field_name} does not exist")

    if allowed_extensions:
        extension = path_obj.suffix.lower()
        if extension not in allowed_extensions:
            ext_str = ", ".join(allowed_extensions)
            return ValidationResult(
                False, f"{field_name} must have one of these extensions: {ext_str}"
            )

    return ValidationResult(True, cleaned_value=path_obj)


def validate_json_data(
    data: Any,
    required_keys: list[str] | None = None,
    schema_validator: Callable[[dict], bool] | None = None,
) -> ValidationResult:
    """
    Validate JSON data structure.
    Args:
        data: Data to validate
        required_keys: List of required keys if data is dict
        schema_validator: Custom validation function
    Returns:
        ValidationResult with validated data
    """
    if data is None:
        return ValidationResult(False, "Data is required")

    if required_keys and isinstance(data, dict):
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            return ValidationResult(
                False, f"Missing required keys: {', '.join(missing_keys)}"
            )

    if schema_validator:
        try:
            if not schema_validator(data):
                return ValidationResult(False, "Data does not match required schema")
        except Exception as e:  # noqa: BLE001
            return ValidationResult(False, f"Schema validation failed: {e}")

    return ValidationResult(True, cleaned_value=data)


class ValidatorChain:
    """Chain multiple validators together."""

    def __init__(self):
        self.validators: list[Callable[[Any], ValidationResult]] = []
        self.field_name = "Value"

    def add(self, validator: Callable[[Any], ValidationResult]) -> ValidatorChain:
        """Add validator to chain."""
        self.validators.append(validator)
        return self

    def set_field_name(self, name: str) -> ValidatorChain:
        """Set field name for error messages."""
        self.field_name = name
        return self

    def validate(self, value: Any) -> ValidationResult:
        """Run all validators in chain."""
        current_value = value

        for validator in self.validators:
            result = validator(current_value)
            if not result.is_valid:
                return ValidationResult(False, result.error_message)
            current_value = result.cleaned_value

        return ValidationResult(True, cleaned_value=current_value)


def sanitize_for_filename(text: str) -> str:
    """
    Sanitize text for use in filename.
    Args:
        text: Text to sanitize
    Returns:
        Sanitized filename-safe text
    """
    # Remove/replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', text)
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)  # Remove control chars
    sanitized = re.sub(r'\s+', '_', sanitized)  # Replace spaces with underscores
    sanitized = sanitized.strip('._')  # Remove leading/trailing dots and underscores

    # Ensure it's not empty
    if not sanitized:
        sanitized = "untitled"

    # Truncate if too long
    if len(sanitized) > 200:
        sanitized = sanitized[:200]

    return sanitized


def sanitize_for_json(data: Any) -> Any:
    """
    Sanitize data for JSON serialization.
    Args:
        data: Data to sanitize
    Returns:
        JSON-safe data
    """
    if data is None:
        return None
    if isinstance(data, (str, int, float, bool)):
        return data
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [sanitize_for_json(item) for item in data]
    # Convert other types to string representation
    return str(data)


# Convenience validator instances
def email_validator(email: str) -> ValidationResult:
    return validate_email(email)


def linkedin_validator(url: str) -> ValidationResult:
    return validate_linkedin_profile(url)


def phone_validator(phone: str) -> ValidationResult:
    return validate_phone(phone)


def url_validator(url: str) -> ValidationResult:
    return validate_url(url)


def uid_validator(uid: str) -> ValidationResult:
    return validate_signalhire_uid(uid)
