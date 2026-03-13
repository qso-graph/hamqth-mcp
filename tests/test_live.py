"""L3 live integration tests for hamqth-mcp — public endpoints only.

Tests the three public (no-auth) HamQTH endpoints against the live API:
  - dxcc (JSON endpoint)
  - dx_spots (CSV endpoint)
  - rbn (JSON endpoint)

Authenticated endpoints (lookup, bio, activity) require HamQTH credentials
and are not tested here.

Run with: pytest tests/test_live.py --live

Test IDs: HAMQTH-L3-001 through HAMQTH-L3-010
"""

from __future__ import annotations

import time

import pytest

from hamqth_mcp.client import HamQTHClient

# Known-good values
KNOWN_CALL_PREFIX = "VP8"  # South Shetland Islands area


@pytest.fixture(autouse=True)
def rate_limit_pause():
    yield
    time.sleep(1)


@pytest.fixture
def client():
    """Fresh HamQTHClient instance — no credentials configured."""
    return HamQTHClient()


# ---------------------------------------------------------------------------
# HAMQTH-L3-001..003: DXCC lookup (public JSON endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_dxcc_live(client):
    """HAMQTH-L3-001: DXCC lookup by callsign returns entity info."""
    result = client.dxcc("W1AW")
    assert "error" not in result, f"DXCC lookup failed: {result}"
    assert result.get("name"), "Missing entity name"
    assert str(result.get("dxcc")) == "291", f"Expected DXCC 291 (United States), got {result.get('dxcc')}"
    assert result.get("continent"), "Missing continent"


@pytest.mark.live
def test_dxcc_by_code_live(client):
    """HAMQTH-L3-002: DXCC lookup by numeric code returns entity."""
    result = client.dxcc("291")
    assert "error" not in result, f"DXCC lookup by code failed: {result}"
    assert "United States" in result.get("name", ""), (
        f"Expected 'United States' in name, got '{result.get('name')}'"
    )


@pytest.mark.live
def test_dxcc_fields_live(client):
    """HAMQTH-L3-003: DXCC result contains all expected fields."""
    result = client.dxcc("W1AW")
    assert "error" not in result, f"DXCC lookup failed: {result}"
    for field in ("callsign", "name", "continent", "dxcc", "cqzone", "ituzone"):
        assert field in result, f"Missing field: {field}"
    # Live API may return int or str — verify value is numeric
    assert str(result["dxcc"]).isdigit(), f"dxcc should be numeric, got {result['dxcc']}"
    assert str(result["cqzone"]).isdigit(), f"cqzone should be numeric, got {result['cqzone']}"


# ---------------------------------------------------------------------------
# HAMQTH-L3-004..006: DX spots (public CSV endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_dx_spots_live(client):
    """HAMQTH-L3-004: DX spots returns a list of spots."""
    spots = client.dx_spots(limit=10)
    assert isinstance(spots, list), f"Expected list, got {type(spots)}"
    # DX cluster is almost always active, but handle empty gracefully
    if len(spots) > 0:
        required = {"call", "freq", "spotter", "datetime", "band", "country"}
        for spot in spots:
            missing = required - spot.keys()
            assert not missing, f"Spot missing fields: {missing}"


@pytest.mark.live
def test_dx_spots_band_filter_live(client):
    """HAMQTH-L3-005: DX spots with band filter returns spots (may be empty)."""
    spots = client.dx_spots(limit=30, band="20M")
    assert isinstance(spots, list), f"Expected list, got {type(spots)}"
    # Band may be quiet — just verify the call didn't error and returned a list


@pytest.mark.live
def test_dx_spots_structure_live(client):
    """HAMQTH-L3-006: DX spot entries have string values for all fields."""
    spots = client.dx_spots(limit=5)
    assert isinstance(spots, list)
    for spot in spots:
        assert isinstance(spot, dict), f"Expected dict, got {type(spot)}"
        for key, value in spot.items():
            assert isinstance(value, str), f"Field '{key}' should be str, got {type(value)}"


# ---------------------------------------------------------------------------
# HAMQTH-L3-007..010: RBN (public JSON endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_rbn_live(client):
    """HAMQTH-L3-007: RBN returns a list of decodes."""
    decodes = client.rbn()
    assert isinstance(decodes, list), f"Expected list, got {type(decodes)}"
    # RBN is almost always active, but handle empty gracefully
    if len(decodes) > 0:
        required = {"call", "freq", "mode", "age"}
        for decode in decodes:
            missing = required - decode.keys()
            assert not missing, f"Decode missing fields: {missing}"


@pytest.mark.live
def test_rbn_mode_filter_live(client):
    """HAMQTH-L3-008: RBN with CW mode filter returns decodes (may be empty)."""
    decodes = client.rbn(mode="CW")
    assert isinstance(decodes, list), f"Expected list, got {type(decodes)}"
    # If results returned, verify mode is CW
    for decode in decodes:
        assert decode.get("mode") == "CW", f"Expected mode CW, got {decode.get('mode')}"


@pytest.mark.live
def test_rbn_age_field_live(client):
    """HAMQTH-L3-009: RBN decode age is an integer (seconds)."""
    decodes = client.rbn()
    assert isinstance(decodes, list)
    for decode in decodes:
        assert isinstance(decode.get("age"), int), (
            f"age should be int, got {type(decode.get('age'))}"
        )


@pytest.mark.live
def test_rbn_band_filter_live(client):
    """HAMQTH-L3-010: RBN with band filter returns decodes (may be empty)."""
    decodes = client.rbn(band="20")
    assert isinstance(decodes, list), f"Expected list, got {type(decodes)}"
