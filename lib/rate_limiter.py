from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class AsyncTokenBucket:
    """A simple async token bucket rate limiter.

    Parameters
    - capacity: maximum number of tokens the bucket can hold
    - refill_rate: tokens added per second (float supported)
    - time_fn: injectable time function returning seconds (monotonic); defaults to loop.time
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        *,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be > 0")
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._tokens = float(capacity)
        self._lock = asyncio.Lock()
        loop = asyncio.get_event_loop()
        self._time = time_fn or loop.time
        self._last = self._time()

    @property
    def available(self) -> float:
        return max(0.0, min(self._tokens, float(self._capacity)))

    async def acquire(self, n: float = 1.0) -> None:
        """Acquire up to ``n`` tokens.

        Notes:
        - ``n`` must be > 0 and <= capacity. Requests larger than capacity cannot be satisfied.
        - Cancellation is supported and will not deadlock the bucket.
        """
        if n <= 0:
            return
        if n > self._capacity:
            raise ValueError("cannot acquire more tokens than capacity")

        while True:
            # Refill and attempt to consume under lock
            async with self._lock:
                now = self._time()
                elapsed = max(0.0, now - self._last)
                if elapsed > 0:
                    self._tokens = min(
                        float(self._capacity),
                        self._tokens + elapsed * self._refill_rate,
                    )
                    self._last = now
                if self._tokens >= n:
                    self._tokens -= n
                    return
                need = n - self._tokens
                wait_s = need / self._refill_rate
            # Sleep outside the lock to allow other waiters to proceed/refill
            await asyncio.sleep(wait_s)
