"""The server spaces its requests to HamQTH, and honours a 429.

Three mechanisms, asserted separately because they were once conflated: the gap
between two requests to one host, how stale a cached answer may be (in the
client), and the interval a provider asks us to wait after a 429. See
qso-graph-devel/planning/MCP-SECURITY-FRAMEWORK.md.

Asserting them because a convention nobody asserts drifts -- which is how
get_version_info drifted across this fleet.
"""

from __future__ import annotations

import time

import pytest

from hamqth_mcp import ratelimit

_A = "https://www.hamqth.com/xml.php"
_B = "https://www.ok2cqr.com/json/dxc.php"


@pytest.fixture(autouse=True)
def _clean() -> None:
    """This module holds process-wide state, so each test starts from none.

    Without it a 429 armed by one test blocks the spacing tests, and the order
    they run in decides whether the suite passes.
    """
    ratelimit.clear()


# --- spacing ---------------------------------------------------------------


def test_min_interval_is_declared_and_positive():
    assert ratelimit.MIN_INTERVAL > 0


def test_consecutive_calls_are_spaced():
    ratelimit.wait(_A)                    # establish the baseline
    start = time.monotonic()
    ratelimit.wait(_A)
    elapsed = time.monotonic() - start
    # Allow a little slack for a slow scheduler, but it must actually wait.
    assert elapsed >= ratelimit.MIN_INTERVAL * 0.8, (
        f"second call returned after {elapsed:.3f}s, "
        f"MIN_INTERVAL is {ratelimit.MIN_INTERVAL}"
    )


def test_a_gap_longer_than_the_interval_is_not_padded():
    ratelimit.wait(_A)
    time.sleep(ratelimit.MIN_INTERVAL * 1.2)
    start = time.monotonic()
    ratelimit.wait(_A)
    # Nothing to wait for: the gap already passed.
    assert time.monotonic() - start < ratelimit.MIN_INTERVAL * 0.5


def test_spacing_is_per_host():
    """One provider's gap must not delay a call to a different provider."""
    ratelimit.wait(_A)
    start = time.monotonic()
    ratelimit.wait(_B)
    if ratelimit.host_of(_A) == ratelimit.host_of(_B):
        pytest.skip("this server reads a single host")
    assert time.monotonic() - start < ratelimit.MIN_INTERVAL * 0.5


def test_host_of_reads_the_host():
    assert ratelimit.host_of("https://example.org/a/b?c=d") == "example.org"
    assert ratelimit.host_of("not a url") == ""


def test_an_unparseable_url_is_still_limited():
    """It shares the "" bucket rather than escaping the limits: the failure to
    avoid is sending the request, not mis-labelling it."""
    ratelimit.wait("garbage")
    start = time.monotonic()
    ratelimit.wait("garbage")
    assert time.monotonic() - start >= ratelimit.MIN_INTERVAL * 0.8


# --- what a 429 does -------------------------------------------------------


def test_backoff_bounds_are_declared():
    assert 0 < ratelimit.MIN_BACKOFF < ratelimit.MAX_BACKOFF


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, ratelimit.MIN_BACKOFF),      # absent: wait the floor, do not guess
        ("", ratelimit.MIN_BACKOFF),
        ("0", ratelimit.MIN_BACKOFF),       # "now" still gets a floor
        ("5", ratelimit.MIN_BACKOFF),       # below the floor is raised to it
        ("300", 300.0),                     # honoured as stated
        ("99999", ratelimit.MAX_BACKOFF),   # above the ceiling is capped
        ("Wed, 21 Oct 2026 07:28:00 GMT", ratelimit.MIN_BACKOFF),  # date unparsed
        ("garbage", ratelimit.MIN_BACKOFF),
    ],
)
def test_retry_after_is_honoured_within_bounds(header, expected):
    assert ratelimit.retry_after(header) == expected


def test_a_block_refuses_the_next_request_without_sleeping():
    """The contract: refuse quickly and say when, never sleep out the wait."""
    waited = ratelimit.block(_A, "300")
    assert waited == 300.0
    start = time.monotonic()
    with pytest.raises(ratelimit.RateLimited) as e:
        ratelimit.wait(_A)
    assert time.monotonic() - start < 1.0, "wait() slept through the backoff"
    assert e.value.retry_after <= 300
    assert str(e.value.retry_after) in str(e.value)


def test_a_block_covers_every_path_on_that_host():
    """A limit is the provider's view of this client, not of one URL."""
    ratelimit.block(_A, "120")
    for suffix in ("", "/other", "?q=1"):
        with pytest.raises(ratelimit.RateLimited):
            ratelimit.wait(_A + suffix)


def test_a_block_does_not_touch_another_host():
    """The reason state is keyed by host: a 429 from one service must not
    silence a different, healthy one for an hour."""
    if ratelimit.host_of(_A) == ratelimit.host_of(_B):
        pytest.skip("this server reads a single host")
    ratelimit.block(_A, "300")
    with pytest.raises(ratelimit.RateLimited):
        ratelimit.wait(_A)
    ratelimit.wait(_B)  # must not raise


def test_the_error_names_the_host_that_limited_us():
    ratelimit.block(_A, "120")
    with pytest.raises(ratelimit.RateLimited) as e:
        ratelimit.wait(_A)
    assert e.value.host == ratelimit.host_of(_A)
    assert ratelimit.host_of(_A) in str(e.value)


def test_clearing_lets_requests_resume():
    ratelimit.block(_A, "120")
    with pytest.raises(ratelimit.RateLimited):
        ratelimit.wait(_A)
    ratelimit.clear()
    ratelimit.wait(_A)  # must not raise


def test_rate_limited_is_a_runtime_error():
    """Callers already handling this client's failures keep working, and
    FastMCP flags the tool result isError either way."""
    assert issubclass(ratelimit.RateLimited, RuntimeError)


# --- the wiring ------------------------------------------------------------
#
# The module above is only useful if the fetch paths actually consult it. These
# assert the join, which is where the earlier version failed: the provider's
# limit was ignored not because nothing could parse Retry-After but because
# nothing looked.


def _http_error(url: str, code: int, **headers: str):
    import urllib.error
    from email.message import Message

    m = Message()
    for k, v in headers.items():
        m[k.replace("_", "-")] = v
    return urllib.error.HTTPError(url, code, "nope", m, None)


def _raises(exc):
    def f(*a: object, **k: object):
        raise exc
    return f


def test_a_429_from_hamqth_arms_the_block(monkeypatch):
    from hamqth_mcp import client as c

    monkeypatch.setattr(
        c.urllib.request, "urlopen", _raises(_http_error(_B, 429, Retry_After="120"))
    )
    cl = c.HamQTHClient()
    with pytest.raises(ratelimit.RateLimited) as e:
        cl._get_text(_B)
    assert e.value.retry_after == 120

    sent: list[str] = []
    monkeypatch.setattr(c.urllib.request, "urlopen", lambda *a, **k: sent.append("x"))
    with pytest.raises(ratelimit.RateLimited):
        cl._get_text(_B)
    assert sent == [], "a request was sent while the host had told us to stop"


def test_a_dx_cluster_429_does_not_stop_callsign_lookups(monkeypatch):
    """The two hosts are separate services. ok2cqr.com limiting us must not
    make hamqth.com lookups fail -- the reason the block is keyed by host."""
    from hamqth_mcp import client as c

    monkeypatch.setattr(
        c.urllib.request, "urlopen", _raises(_http_error(_B, 429, Retry_After="300"))
    )
    cl = c.HamQTHClient()
    with pytest.raises(ratelimit.RateLimited):
        cl._get_text(_B)

    reached: list[str] = []

    class Resp:
        def read(self) -> bytes:
            reached.append("sent")
            return b"<HamQTH/>"

        def __enter__(self) -> "Resp":
            return self

        def __exit__(self, *a: object) -> None:
            return None

    monkeypatch.setattr(c.urllib.request, "urlopen", lambda *a, **k: Resp())
    cl._get_xml(_A)
    assert reached == ["sent"], "hamqth.com was blocked by ok2cqr.com's limit"


def test_a_429_is_not_reported_as_a_network_problem(monkeypatch):
    """The old behaviour: every failure became "check network connectivity",
    so a rate limit was indistinguishable from a cable being out."""
    from hamqth_mcp import client as c

    monkeypatch.setattr(
        c.urllib.request, "urlopen", _raises(_http_error(_B, 429, Retry_After="90"))
    )
    cl = c.HamQTHClient()
    with pytest.raises(RuntimeError) as e:
        cl._get_json(_B)
    assert "network" not in str(e.value).lower()
    assert "rate limiting" in str(e.value)


def test_a_500_leaks_neither_password_nor_url(monkeypatch):
    """The login URL carries the password, so no message may name it."""
    from hamqth_mcp import client as c

    monkeypatch.setattr(c.urllib.request, "urlopen", _raises(_http_error(_A, 500)))
    cl = c.HamQTHClient()
    with pytest.raises(RuntimeError) as e:
        cl._get_xml(_A + "?u=x&p=SECRET")
    assert "SECRET" not in str(e.value)
    assert "hamqth.com" not in str(e.value)
    assert not isinstance(e.value, ratelimit.RateLimited)
