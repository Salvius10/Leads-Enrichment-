import logging
import sys
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def setup_error_logging():
    """Setup basic error logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )


def log_errors(func: Callable) -> Callable:
    """Decorator to log errors in functions."""

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise

    return wrapper


def safe_json_load(file_path: str) -> Any:
    """Safely load JSON with error handling."""
    import json

    try:
        with open(file_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Failed to load JSON from {file_path}: {e}")
        raise ValueError(f"Invalid JSON file: {file_path}") from e


def safe_file_write(file_path: str, data: str):
    """Safely write to file with error handling."""
    try:
        with open(file_path, 'w') as f:
            f.write(data)
    except OSError as e:
        logger.error(f"Failed to write to {file_path}: {e}")
        raise
