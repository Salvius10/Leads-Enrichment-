"""
SignalHire Agent library modules.

This package contains reusable library components for the SignalHire agent,
including utilities for browser automation, rate limiting, configuration,
async operations, validation, and other shared functionality.
"""

# Import commonly used utilities for easy access
from .async_utils import (
    AsyncContextTimer,
    AsyncQueue,
    AsyncRateLimiter,
    async_cache,
    async_filter,
    async_map,
    gather_with_concurrency,
    retry_async,
    run_async,
    run_with_progress,
    with_timeout,
)
from .common import (
    CircuitBreaker,
    TimingContext,
    chunk_list,
    debounce,
    flatten_dict,
    format_bytes,
    format_duration,
    is_valid_email,
    is_valid_linkedin_profile,
    is_valid_phone,
    safe_format_datetime,
    safe_get_nested,
    sanitize_filename,
    truncate_string,
    validate_url,
)
from .contact_cache import ContactCache, CachedContact, normalize_contacts
from .config import (
    get_api_config,
    get_callback_server_config,
    get_config,
    get_export_config,
    get_rate_limit_config,
    get_signalhire_credentials,
    load_config,
)
from .validation import (
    ValidationResult,
    ValidatorChain,
    sanitize_for_filename,
    sanitize_for_json,
    validate_choice,
    validate_email,
    validate_file_path,
    validate_integer_range,
    validate_json_data,
    validate_linkedin_profile,
    validate_phone,
    validate_signalhire_uid,
    validate_string_length,
)
from .signalhire_client import SignalHireClient, APIResponse, SignalHireAPIError
from .callback_server import CallbackServer, get_server

__all__ = [
    # Async utilities
    "AsyncContextTimer",
    "AsyncQueue",
    "AsyncRateLimiter",
    "async_cache",
    "async_filter",
    "async_map",
    "gather_with_concurrency",
    "retry_async",
    "run_async",
    "run_with_progress",
    "with_timeout",
    # Common utilities
    "CircuitBreaker",
    "TimingContext",
    "chunk_list",
    "debounce",
    "flatten_dict",
    "format_bytes",
    "format_duration",
    "is_valid_email",
    "is_valid_linkedin_profile",
    "is_valid_phone",
    "safe_format_datetime",
    "safe_get_nested",
    "sanitize_filename",
    "truncate_string",
    "validate_url",
    # Contact cache
    "ContactCache",
    "CachedContact",
    "normalize_contacts",
    # Configuration
    "get_api_config",
    "get_callback_server_config",
    "get_config",
    "get_export_config",
    "get_rate_limit_config",
    "get_signalhire_credentials",
    "load_config",
    # Validation
    "ValidationResult",
    "ValidatorChain",
    "sanitize_for_filename",
    "sanitize_for_json",
    "validate_choice",
    "validate_email",
    "validate_file_path",
    "validate_integer_range",
    "validate_json_data",
    "validate_linkedin_profile",
    "validate_phone",
    "validate_signalhire_uid",
    "validate_string_length",
    # SignalHire client
    "SignalHireClient",
    "APIResponse",
    "SignalHireAPIError",
    # Callback server
    "CallbackServer",
    "get_server",
]
