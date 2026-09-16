"""
Common utilities and shared functionality for SignalHire Agent.

This module contains reusable utilities that are used across multiple components
to reduce code duplication and improve maintainability.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

T = TypeVar('T')


def safe_get_nested(data: dict[str, Any], keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary values using dot notation.
    Args:
        data: Dictionary to search
        keys: Dot-separated key path (e.g., "user.profile.name")
        default: Default value if key not found
    Returns:
        Value at the nested key or default
    Example:
        >>> data = {"user": {"profile": {"name": "John"}}}
        >>> safe_get_nested(data, "user.profile.name")
        "John"
        >>> safe_get_nested(data, "user.profile.age", 25)
        25
    """
    try:
        value = data
        for key in keys.split('.'):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    except (AttributeError, TypeError):
        return default


def safe_format_datetime(
    dt: datetime | str | None,
    format_str: str = "%Y-%m-%d %H:%M:%S",
    default: str = "N/A",
) -> str:
    """
    Safely format a datetime object or string.
    Args:
        dt: Datetime object, ISO string, or None
        format_str: Format string for output
        default: Default value if datetime is None or invalid
    Returns:
        Formatted datetime string or default
    """
    if dt is None:
        return default

    try:
        if isinstance(dt, str):
            # Try parsing ISO format
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))

        if isinstance(dt, datetime):
            return dt.strftime(format_str)
    except (ValueError, AttributeError):
        pass

    return default


def truncate_string(
    text: str | None, max_length: int = 100, suffix: str = "..."
) -> str:
    """
    Truncate a string to a maximum length with optional suffix.
    Args:
        text: String to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add if truncated
    Returns:
        Truncated string
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename by removing invalid characters.
    Args:
        filename: Original filename
        max_length: Maximum filename length
    Returns:
        Sanitized filename safe for filesystem
    """
    import re

    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # Remove control characters
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32)

    # Truncate if too long
    if len(sanitized) > max_length:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        max_name_length = max_length - len(ext)
        sanitized = name[:max_name_length] + ext

    return sanitized.strip('.')


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes value in human-readable format.
    Args:
        bytes_value: Number of bytes
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    if bytes_value == 0:
        return "0 B"

    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(bytes_value)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.
    Args:
        seconds: Duration in seconds
    Returns:
        Formatted duration string
    """
    if seconds < 0:
        return "0s"

    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours < 24:
        return f"{hours}h {remaining_minutes}m"

    days = hours // 24
    remaining_hours = hours % 24

    return f"{days}d {remaining_hours}h"


def normalize_path_for_display(path: str | Path | None) -> str:
    """Normalize filesystem paths for display in WSL/Windows environments.

    Converts Windows UNC or drive-style paths that point into the WSL
    filesystem into POSIX-style paths so users can easily navigate to the
    location from a WSL shell. Standard POSIX paths are returned unchanged.
    """

    if path is None:
        return ""

    path_str = str(path)
    if not path_str:
        return path_str

    normalized = path_str.replace("\\", "/")
    lower_normalized = normalized.lower()

    wsl_prefixes = (
        "//?/unc/wsl.localhost/",
        "//?/unc/wsl$/",
        "//wsl.localhost/",
        "//wsl$/",
    )

    for prefix in wsl_prefixes:
        if lower_normalized.startswith(prefix):
            trimmed = normalized[len(prefix) :].lstrip("/")
            segments = [segment for segment in trimmed.split("/") if segment]
            if segments:
                # Drop the distro name segment to produce a Linux-style path
                segments = segments[1:] if len(segments) > 1 else []
            return "/" + "/".join(segments) if segments else "/"

    drive_match = re.match(r"^([a-zA-Z]):/(.*)$", normalized)
    if drive_match:
        drive = drive_match.group(1).lower()
        remainder = drive_match.group(2)
        return f"/mnt/{drive}/{remainder}" if remainder else f"/mnt/{drive}"

    return normalized


def debounce(wait_seconds: float):
    """
    Decorator to debounce function calls.
    Args:
        wait_seconds: Minimum time between calls
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T | None]:
        last_called = {'time': 0.0}

        @wraps(func)
        def wrapper(*args, **kwargs) -> T | None:
            now = time.time()
            if now - last_called['time'] >= wait_seconds:
                last_called['time'] = now
                return func(*args, **kwargs)
            return None

        return wrapper

    return decorator


async def batch_process(
    items: list[T],
    process_func: Callable[[T], Any],
    batch_size: int = 10,
    delay_between_batches: float = 0.1,
) -> list[Any]:
    """
    Process items in batches to avoid overwhelming systems.
    Args:
        items: Items to process
        process_func: Function to process each item
        batch_size: Number of items per batch
        delay_between_batches: Delay between batches in seconds
    Returns:
        List of processed results
    """
    results = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]

        if asyncio.iscoroutinefunction(process_func):
            batch_results = await asyncio.gather(
                *[process_func(item) for item in batch]
            )
        else:
            batch_results = [process_func(item) for item in batch]

        results.extend(batch_results)

        # Add delay between batches (except for last batch)
        if i + batch_size < len(items) and delay_between_batches > 0:
            await asyncio.sleep(delay_between_batches)

    return results


class TimingContext:
    """Context manager for timing operations."""

    def __init__(self, operation_name: str, logger_instance: Any | None = None):
        self.operation_name = operation_name
        self.logger = logger_instance or logger
        self.start_time: float | None = None
        self.end_time: float | None = None

    def __enter__(self) -> TimingContext:
        self.start_time = time.time()
        self.logger.debug("Starting operation", operation=self.operation_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time

        if exc_type is None:
            self.logger.info(
                "Operation completed",
                operation=self.operation_name,
                duration_seconds=round(duration, 3),
                duration_formatted=format_duration(duration),
            )
        else:
            self.logger.error(
                "Operation failed",
                operation=self.operation_name,
                duration_seconds=round(duration, 3),
                error=str(exc_val),
            )

    @property
    def duration(self) -> float | None:
        """Get operation duration if completed."""
        if self.start_time is not None and self.end_time is not None:
            return self.end_time - self.start_time
        return None


class CircuitBreaker:
    """Simple circuit breaker implementation for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise Exception(f"Circuit breaker is OPEN for {func.__name__}")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e

        return wrapper

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                "Circuit breaker opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
            )


def validate_url(url: str) -> bool:
    """
    Validate if a string is a valid URL.
    Args:
        url: URL string to validate
    Returns:
        True if valid URL, False otherwise
    """
    import re

    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)',
        re.IGNORECASE,
    )

    return url_pattern.match(url) is not None


def chunk_list(items: list[T], chunk_size: int) -> list[list[T]]:
    """
    Split a list into chunks of specified size.
    Args:
        items: List to chunk
        chunk_size: Size of each chunk
    Returns:
        List of chunks
    """
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def flatten_dict(data: dict[str, Any], separator: str = '.') -> dict[str, Any]:
    """
    Flatten a nested dictionary.
    Args:
        data: Dictionary to flatten
        separator: Separator for nested keys
    Returns:
        Flattened dictionary
    """

    def _flatten(obj: Any, parent_key: str = '', sep: str = '.') -> dict[str, Any]:
        items = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                items.extend(_flatten(v, new_key, sep=sep).items())
        else:
            return {parent_key: obj}
        return dict(items)

    return _flatten(data, sep=separator)


# Commonly used regex patterns
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
LINKEDIN_PROFILE_PATTERN = re.compile(r'^https?://(?:www\.)?linkedin\.com/in/[\w-]+/?$')
PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')


def is_valid_email(email: str) -> bool:
    """Check if string is a valid email address."""
    return bool(EMAIL_PATTERN.match(email.strip()))


def is_valid_linkedin_profile(url: str) -> bool:
    """Check if string is a valid LinkedIn profile URL."""
    return bool(LINKEDIN_PROFILE_PATTERN.match(url.strip()))


def is_valid_phone(phone: str) -> bool:
    """Check if string is a valid phone number."""
    # Remove common separators and spaces
    cleaned = re.sub(r'[\s\-\(\)]+', '', phone.strip())
    return bool(PHONE_PATTERN.match(cleaned))
