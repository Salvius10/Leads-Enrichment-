from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def async_retry(
    *,
    retries: int = 3,
    base_delay: float = 0.05,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
):
    """Retry an async function on failure with optional exponential backoff.

    Usage:
        @async_retry(retries=2)
        async def fn(...):
            ...
    """

    def decorator(func: Callable[..., Awaitable[Any]]):
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            delay = base_delay
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions:
                    attempt += 1
                    if attempt > retries:
                        raise
                    d = delay * (2 ** (attempt - 1))
                    if jitter:
                        d *= random.uniform(0.8, 1.2)
                    await sleep(d)

        return wrapper

    return decorator
