"""A small per-user rate limiter.

Two endpoints spend real money on every call - bill extraction burns Gemini
quota, and minting a browser agent session opens a billable AssemblyAI
session. Neither had any limit, so a single account could exhaust both.

In-process and therefore per-replica: with one instance that is exact, and with
several it becomes a limit per instance rather than per cluster. That is a
deliberate trade for now - it is honest about what it is, and it is far better
than nothing. Move it to Redis alongside the event bus when scaling out.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException

_hits: dict[str, deque[float]] = defaultdict(deque)


def limit(key: str, *, max_calls: int, per_seconds: float) -> None:
    """Allow max_calls in any rolling window, or raise 429."""
    now = time.monotonic()
    window = _hits[key]

    while window and now - window[0] > per_seconds:
        window.popleft()

    if len(window) >= max_calls:
        retry_after = int(per_seconds - (now - window[0])) + 1
        raise HTTPException(
            status_code=429,
            detail="rate_limited: too many requests, try again shortly",
            headers={"Retry-After": str(retry_after)},
        )

    window.append(now)

    # Keys are user ids, so the map would grow with the user base; drop the
    # ones that have gone quiet.
    if len(_hits) > 5000:
        for stale in [k for k, w in _hits.items() if not w or now - w[-1] > per_seconds * 4]:
            _hits.pop(stale, None)


def reset() -> None:
    """Test helper - the limiter is process-wide state."""
    _hits.clear()
