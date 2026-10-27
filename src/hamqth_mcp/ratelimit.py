"""Spacing between requests to HamQTH (hamqth.com and ok2cqr.com).

HamQTH publishes no request limit. Most endpoints are public and the rest need
a free account, which is an invitation to be reasonable rather than a quota, so
this server spaces its requests rather than sending them as fast as they are
asked for.

This is not throttling the user (KI7MT, 2026-10-11): it limits what this server
sends to somebody else's service, and does not limit the person asking. The
cache in client.py, holding sessions 55 s and lookups 300 s does the larger share of the
work -- it removes requests rather than delaying them -- and this covers what the
cache cannot: a model calling tools in a loop over inputs that each miss.
"""

from __future__ import annotations

import threading
import time
from typing import Final

# Seconds between outbound requests.
# Matched to the fleet's default where a provider states nothing: sota-mcp and
# iota-mcp use the same 200 ms, iota's comment calling it "good neighbor". Not
# invented here, and not claimed to be HamQTH's published figure, because
# there is none.
MIN_INTERVAL: Final[float] = 0.2

_lock = threading.Lock()
_last: float = 0.0


class RateLimited(RuntimeError):
    """HamQTH asked us to stop. The message is safe to show a user.

    A RuntimeError subclass so callers that already handle this client's
    failures keep working, and so FastMCP flags the tool result isError either
    way.
    """

    def __init__(self, wait_seconds: float) -> None:
        self.retry_after = max(1, round(wait_seconds))
        super().__init__(
            "HamQTH is rate limiting this client; try again in "
            f"{self.retry_after} s"
        )


def wait() -> None:
    """Block until MIN_INTERVAL has passed since the previous request.

    Held across threads by one lock, so concurrent tool calls queue rather than
    each measuring their own gap and all firing at once.

    Raises RateLimited if HamQTH has told us to stop and the interval it
    asked for has not passed. It does not sleep through that wait: an MCP server
    answers a synchronous tool call behind a client timeout, so waiting out an
    hour inside one is a hang rather than restraint. It refuses, and the message
    says when to come back.
    """
    global _last
    with _lock:
        remaining = _blocked_until - time.monotonic()
        if remaining > 0:
            raise RateLimited(remaining)
        elapsed = time.monotonic() - _last
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        _last = time.monotonic()


# --- what to do when HamQTH says stop ---------------------------------
#
# A 429 carrying Retry-After is the provider stating its limit outright, and it
# is the most explicit form of the stated limit guarantee 8 requires honouring.
# The interval is bounded rather than taken verbatim: a header asking for a day
# would strand an interactive tool, and one asking for nothing would let us
# hammer. See qso-graph-devel/planning/MCP-SECURITY-FRAMEWORK.md.
MIN_BACKOFF: Final[float] = 60.0
MAX_BACKOFF: Final[float] = 3600.0

_blocked_until: float = 0.0


def retry_after(header: str | None) -> float:
    """Seconds to wait, from a Retry-After header, clamped to our bounds.

    Retry-After may also be an HTTP date. That form is not parsed and falls back
    to the floor rather than guessing, because a wrong parse would either hammer
    HamQTH or strand the user.
    """
    try:
        seconds = float(header) if header else 0.0
    except ValueError:
        seconds = 0.0
    return min(max(seconds, MIN_BACKOFF), MAX_BACKOFF)


def block(header: str | None) -> float:
    """Honour a 429: stop sending for the interval it asked for.

    Returns that interval, for the error the caller raises. It covers every
    endpoint, because a limit is HamQTH's view of this client and not of one
    path.
    """
    global _blocked_until
    seconds = retry_after(header)
    with _lock:
        _blocked_until = time.monotonic() + seconds
    return seconds


def clear() -> None:
    """Forget the block. For tests, which share this module's state."""
    global _blocked_until, _last
    with _lock:
        _blocked_until = 0.0
        _last = 0.0
