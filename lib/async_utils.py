"""
Async utilities for SignalHire Agent.

This module provides reusable async utilities and patterns used across
the application for better async/await handling and performance.
"""

from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

from .common import format_duration

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = structlog.get_logger(__name__)

T = TypeVar('T')


async def with_timeout(
    coro: Awaitable[T], timeout_seconds: float, timeout_message: str | None = None
) -> T:
    """
    Execute a coroutine with a timeout.
    Args:
        coro: Coroutine to execute
        timeout_seconds: Timeout in seconds
        timeout_message: Custom timeout message
    Returns:
        Result of coroutine
    Raises:
        asyncio.TimeoutError: If timeout exceeded
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError as e:
        message = timeout_message or f"Operation timed out after {timeout_seconds}s"
        logger.warning(
            "Async operation timeout", timeout_seconds=timeout_seconds, message=message
        )
        raise TimeoutError(message) from e


async def retry_async(
    func: Callable[..., Awaitable[T]],
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    exponential_backoff: bool = True,
    exceptions: tuple = (Exception,),
) -> T:
    """
    Retry an async function with exponential backoff.
    Args:
        func: Async function to retry
        max_attempts: Maximum number of attempts
        delay_seconds: Initial delay between attempts
        exponential_backoff: Use exponential backoff
        exceptions: Exceptions to catch and retry on
    Returns:
        Result of successful function call
    Raises:
        Last exception if all attempts fail
    """
    last_exception = None

    for attempt in range(max_attempts):
        try:
            return await func()
        except exceptions as e:
            last_exception = e

            if attempt == max_attempts - 1:
                logger.error(
                    "All retry attempts failed",
                    function=func.__name__,
                    attempts=max_attempts,
                    error=str(e),
                )
                raise e

            delay = delay_seconds
            if exponential_backoff:
                delay *= 2**attempt

            logger.warning(
                "Async operation failed, retrying",
                function=func.__name__,
                attempt=attempt + 1,
                max_attempts=max_attempts,
                delay_seconds=delay,
                error=str(e),
            )

            await asyncio.sleep(delay)

    # This should never be reached, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry loop finished without returning or raising.")


async def gather_with_concurrency(
    awaitables: list[Awaitable[T]], concurrency_limit: int = 10
) -> list[T]:
    """
    Execute awaitables with concurrency limit.
    Args:
        awaitables: List of awaitables to execute
        concurrency_limit: Maximum concurrent executions
    Returns:
        List of results in original order
    """
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def bounded_awaitable(awaitable: Awaitable[T]) -> T:
        async with semaphore:
            return await awaitable

    bounded_awaitables = [bounded_awaitable(aw) for aw in awaitables]
    return await asyncio.gather(*bounded_awaitables)


async def run_with_progress(
    awaitables: list[Awaitable[T]],
    progress_callback: Callable[[int, int], None] | None = None,
    concurrency_limit: int = 10,
) -> list[T]:
    """
    Run awaitables with progress tracking.
    Args:
        awaitables: List of awaitables to execute
        progress_callback: Callback for progress updates (completed, total)
        concurrency_limit: Maximum concurrent executions
    Returns:
        List of results in original order
    """
    total = len(awaitables)
    completed = 0
    results: list[T | Exception] = [None] * total  # Pre-allocate results list

    semaphore = asyncio.Semaphore(concurrency_limit)

    async def execute_with_progress(index: int, awaitable: Awaitable[T]) -> None:
        nonlocal completed
        async with semaphore:
            try:
                result = await awaitable
                results[index] = result
            except Exception as e:  # noqa: BLE001
                results[index] = e
            finally:
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

    # Start all tasks
    tasks = [
        asyncio.create_task(execute_with_progress(i, aw))
        for i, aw in enumerate(awaitables)
    ]

    # Wait for completion
    await asyncio.gather(*tasks, return_exceptions=True)

    # Re-raise any exceptions
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Task {i} failed", error=str(result))
            raise result

    return results


class AsyncContextTimer:
    """Async context manager for timing operations."""

    def __init__(self, operation_name: str, logger_instance: Any | None = None):
        self.operation_name = operation_name
        self.logger = logger_instance or logger
        self.start_time: float | None = None
        self.end_time: float | None = None

    async def __aenter__(self) -> AsyncContextTimer:
        self.start_time = time.time()
        self.logger.debug("Starting async operation", operation=self.operation_name)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time

        if exc_type is None:
            self.logger.info(
                "Async operation completed",
                operation=self.operation_name,
                duration_seconds=round(duration, 3),
                duration_formatted=format_duration(duration),
            )
        else:
            self.logger.error(
                "Async operation failed",
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


def async_cache(ttl_seconds: float = 300):
    """
    Simple async function cache decorator with TTL.
    Args:
        ttl_seconds: Cache time-to-live in seconds
    """
    cache = {}

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Create cache key from arguments
            cache_key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()

            # Check if cached result is still valid
            if cache_key in cache:
                cached_result, cached_time = cache[cache_key]
                if current_time - cached_time < ttl_seconds:
                    logger.debug("Returning cached result", function=func.__name__)
                    return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache[cache_key] = (result, current_time)

            # Clean up expired entries periodically
            if len(cache) > 100:  # Arbitrary limit
                expired_keys = [
                    k
                    for k, (_, cached_time) in cache.items()
                    if current_time - cached_time >= ttl_seconds
                ]
                for k in expired_keys:
                    cache.pop(k, None)

            return result

        # Add cache clearing method
        wrapper.clear_cache = lambda: cache.clear()
        return wrapper

    return decorator


class AsyncQueue:
    """Enhanced async queue with additional features."""

    def __init__(self, maxsize: int = 0):
        self._queue = asyncio.Queue(maxsize=maxsize)
        self._finished = False
        self._stats = {'items_added': 0, 'items_processed': 0, 'processing_errors': 0}

    async def put(self, item: T) -> None:
        """Add item to queue."""
        if self._finished:
            raise RuntimeError("Cannot add items to finished queue")

        await self._queue.put(item)
        self._stats['items_added'] += 1

    async def get(self) -> T:
        """Get item from queue."""
        item = await self._queue.get()
        self._stats['items_processed'] += 1
        return item

    def task_done(self) -> None:
        """Mark task as done."""
        self._queue.task_done()

    def record_error(self) -> None:
        """Record processing error."""
        self._stats['processing_errors'] += 1

    async def join(self) -> None:
        """Wait for all tasks to complete."""
        await self._queue.join()

    def finish(self) -> None:
        """Mark queue as finished."""
        self._finished = True

    def qsize(self) -> int:
        """Get queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()

    def full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()

    @property
    def stats(self) -> dict:
        """Get queue statistics."""
        return self._stats.copy()


async def async_map(
    func: Callable[[T], Awaitable[Any]], items: list[T], concurrency: int = 10
) -> list[Any]:
    """
    Async version of map() with concurrency control.
    Args:
        func: Async function to apply
        items: Items to process
        concurrency: Maximum concurrent executions
    Returns:
        List of results
    """
    awaitables = [func(item) for item in items]
    return await gather_with_concurrency(awaitables, concurrency)


async def async_filter(
    predicate: Callable[[T], Awaitable[bool]], items: list[T], concurrency: int = 10
) -> list[T]:
    """
    Async version of filter() with concurrency control.
    Args:
        predicate: Async predicate function
        items: Items to filter
        concurrency: Maximum concurrent executions
    Returns:
        Filtered list
    """
    results = await async_map(predicate, items, concurrency)
    return [item for item, keep in zip(items, results, strict=False) if keep]


class AsyncRateLimiter:
    """Simple async rate limiter."""

    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until rate limit allows another call."""
        async with self.lock:
            now = time.time()

            # Remove old calls outside the time window
            self.calls = [
                call_time
                for call_time in self.calls
                if now - call_time < self.time_window
            ]

            # If we're at the limit, wait
            if len(self.calls) >= self.max_calls:
                sleep_time = self.time_window - (now - self.calls[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    await self.acquire()  # Retry after waiting
                    return

            # Record this call
            self.calls.append(now)


def run_async(coro: Awaitable[T]) -> T:
    """
    Run an async function in a sync context.
    Args:
        coro: Coroutine to run
    Returns:
        Result of coroutine
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
