"""In-process pub/sub for live call events, consumed by the dashboard's SSE feed.

One negotiation call has exactly one bridge writing to it and typically one
browser reading it, so this deliberately stays a dict of asyncio queues rather
than Redis or Pub/Sub. It does not survive a restart or span replicas - the
authoritative record of a call is the recording and its post-call transcript
(app/services/verification.py), not this.

A short replay buffer is kept per task so a browser that connects mid-call, or
reconnects after a dropped SSE stream, still renders the turns it missed
instead of showing an empty transcript beside a call already in progress.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

REPLAY_LIMIT = 200
QUEUE_LIMIT = 500
# A call's replay buffer is only useful while the call is live or being read.
# Without eviction every negotiation the process ever saw kept 200 events
# forever - a slow, permanent memory climb.
REPLAY_TTL_SECONDS = 60 * 60
# A hard ceiling as well as a TTL, so a burst can't outrun expiry.
MAX_TRACKED_CALLS = 500

# A per-call counter stamped onto every event. The replay buffer is delivered
# again to every new subscriber, and a browser reconnects repeatedly during a
# call - the platform cuts the stream about once a minute - so without a
# sequence number the transcript grew a fresh copy of itself each time.
_sequence: dict[str, int] = defaultdict(int)

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_replay: dict[str, deque] = defaultdict(lambda: deque(maxlen=REPLAY_LIMIT))
_last_seen: dict[str, float] = {}


def _evict() -> None:
    """Drop buffers for calls that ended long ago, oldest first."""
    now = time.monotonic()
    for task_id in [t for t, seen in _last_seen.items() if now - seen > REPLAY_TTL_SECONDS]:
        # Never evict a call somebody is still watching.
        if not _subscribers.get(task_id):
            _replay.pop(task_id, None)
            _last_seen.pop(task_id, None)
            _sequence.pop(task_id, None)

    # An empty subscriber set is a call nobody is watching any more; the entry
    # itself would otherwise outlive every call the process ever served.
    for task_id in [t for t, subs in _subscribers.items() if not subs]:
        _subscribers.pop(task_id, None)

    while len(_replay) > MAX_TRACKED_CALLS:
        oldest = min(_last_seen, key=_last_seen.get, default=None)
        if oldest is None:
            break
        _replay.pop(oldest, None)
        _last_seen.pop(oldest, None)
        _sequence.pop(oldest, None)


def publish(task_id: str, event: dict[str, Any]) -> None:
    """Fan an event out to every live subscriber. Never blocks and never raises -
    a stalled browser must not be able to wedge an in-progress phone call.

    Each event is stamped with a per-call sequence number so a reader that has
    seen it before - on a replay after reconnecting - can tell.
    """
    _sequence[task_id] += 1
    event = {**event, "seq": _sequence[task_id]}
    _replay[task_id].append(event)
    _last_seen[task_id] = time.monotonic()
    _evict()
    for queue in list(_subscribers.get(task_id, ())):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Dropping event for task %s: subscriber queue full", task_id)


async def subscribe(task_id: str) -> AsyncIterator[dict[str, Any]]:
    """Yields the replay buffer first, then every subsequent event."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_LIMIT)
    _subscribers[task_id].add(queue)
    try:
        for event in list(_replay[task_id]):
            yield event
        while True:
            yield await queue.get()
    finally:
        _subscribers[task_id].discard(queue)
        if not _subscribers[task_id]:
            _subscribers.pop(task_id, None)


def history(task_id: str) -> list[dict[str, Any]]:
    return list(_replay[task_id])


def clear(task_id: str) -> None:
    _replay.pop(task_id, None)
    _last_seen.pop(task_id, None)
    _sequence.pop(task_id, None)


def tracked_calls() -> int:
    """How many buffers are held. Exposed so the eviction is testable."""
    return len(_replay)
