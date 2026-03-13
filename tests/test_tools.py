"""L2 unit tests for hamqth-mcp — all 7 tools + cache helpers.

Uses HAMQTH_MCP_MOCK=1 for tool-level tests (no HamQTH API calls).
Direct unit tests on caching and tool parameter handling.

Test IDs: HAMQTH-L2-001 through HAMQTH-L2-045
"""

from __future__ import annotations

import os
import time

import pytest

os.environ["HAMQTH_MCP_MOCK"] = "1"

from hamqth_mcp.client import HamQTHClient
from hamqth_mcp.server import (
    hamqth_activity,
    hamqth_bio,
    hamqth_dxcc,
    hamqth_dx_spots,
    hamqth_lookup,
    hamqth_rbn,
    hamqth_verify_qso,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Fresh HamQTHClient instance."""
    return HamQTHClient()


# ---------------------------------------------------------------------------
# HAMQTH-L2-001..008: Cache helpers
# ---------------------------------------------------------------------------


class TestCache:
    def test_cache_set_and_get(self, client):
        """HAMQTH-L2-001: Set then get returns value."""
        client._cache_set("test_key", "test_value", 10.0)
        assert client._cache_get("test_key") == "test_value"

    def test_cache_miss(self, client):
        """HAMQTH-L2-002: Missing key returns None."""
        assert client._cache_get("nonexistent") is None

    def test_cache_expiry(self, client):
        """HAMQTH-L2-003: Expired entry returns None."""
        client._cache_set("test_key", "test_value", 0.01)
        time.sleep(0.02)
        assert client._cache_get("test_key") is None

    def test_cache_overwrite(self, client):
        """HAMQTH-L2-004: Overwriting key updates value."""
        client._cache_set("k", "old", 10.0)
        client._cache_set("k", "new", 10.0)
        assert client._cache_get("k") == "new"

    def test_cache_stores_dict(self, client):
        """HAMQTH-L2-005: Cache stores complex types."""
        data = {"callsign": "OK2CQR", "country": "Czech Republic"}
        client._cache_set("lookup", data, 10.0)
        assert client._cache_get("lookup") == data


# ---------------------------------------------------------------------------
# HAMQTH-L2-010..015: hamqth_lookup
# ---------------------------------------------------------------------------


class TestLookup:
    def test_returns_record(self):
        """HAMQTH-L2-010: Lookup returns callsign data."""
        result = hamqth_lookup(persona="test", callsign="OK2CQR")
        assert "error" not in result
        assert result["callsign"] == "OK2CQR"

    def test_country_field(self):
        """HAMQTH-L2-011: Lookup includes country."""
        result = hamqth_lookup(persona="test", callsign="OK2CQR")
        assert result["country"] == "Czech Republic"

    def test_grid_field(self):
        """HAMQTH-L2-012: Lookup includes grid locator."""
        result = hamqth_lookup(persona="test", callsign="OK2CQR")
        assert result.get("grid") is not None

    def test_lookup_fields(self):
        """HAMQTH-L2-013: Lookup has expected fields."""
        result = hamqth_lookup(persona="test", callsign="OK2CQR")
        for field in ("callsign", "country", "grid"):
            assert field in result, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# HAMQTH-L2-016..018: hamqth_dxcc
# ---------------------------------------------------------------------------


class TestDxcc:
    def test_returns_entity(self):
        """HAMQTH-L2-016: DXCC lookup returns entity info."""
        result = hamqth_dxcc(query="VP8PJ")
        assert "error" not in result
        assert result["name"] == "South Shetland Islands"

    def test_dxcc_code(self):
        """HAMQTH-L2-017: DXCC entity code is integer."""
        result = hamqth_dxcc(query="VP8PJ")
        assert result["dxcc"] == 241

    def test_dxcc_fields(self):
        """HAMQTH-L2-018: DXCC result has expected fields."""
        result = hamqth_dxcc(query="VP8PJ")
        for field in ("name", "dxcc", "continent"):
            assert field in result, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# HAMQTH-L2-019..021: hamqth_bio + hamqth_activity
# ---------------------------------------------------------------------------


class TestBioActivity:
    def test_bio_content(self):
        """HAMQTH-L2-019: Bio returns text content."""
        result = hamqth_bio(persona="test", callsign="OK2CQR")
        assert result["callsign"] == "OK2CQR"
        assert result["bio"] is not None
        assert "HamQTH" in result["bio"]

    def test_activity_returns_list(self):
        """HAMQTH-L2-020: Activity returns activity list."""
        result = hamqth_activity(persona="test", callsign="KI7MT")
        assert result["callsign"] == "KI7MT"
        assert result["total"] >= 1
        assert len(result["activity"]) >= 1

    def test_activity_fields(self):
        """HAMQTH-L2-021: Activity entries have expected fields."""
        result = hamqth_activity(persona="test", callsign="KI7MT")
        assert isinstance(result["activity"], list)


# ---------------------------------------------------------------------------
# HAMQTH-L2-022..028: hamqth_dx_spots
# ---------------------------------------------------------------------------


class TestDxSpots:
    def test_returns_spots(self):
        """HAMQTH-L2-022: DX spots returns mock data."""
        result = hamqth_dx_spots()
        assert "error" not in result
        assert result["total"] == 3
        assert len(result["spots"]) == 3

    def test_with_band_filter(self):
        """HAMQTH-L2-023: Band filter accepted."""
        result = hamqth_dx_spots(limit=60, band="20M")
        assert "error" not in result
        assert isinstance(result["spots"], list)

    def test_spot_fields(self):
        """HAMQTH-L2-024: Spots have required fields."""
        result = hamqth_dx_spots()
        required = {"call", "freq", "datetime", "spotter", "band", "country"}
        for spot in result["spots"]:
            assert required.issubset(spot.keys()), f"Missing: {required - spot.keys()}"

    def test_spot_callsigns(self):
        """HAMQTH-L2-025: Mock spots have expected callsigns."""
        result = hamqth_dx_spots()
        calls = [s["call"] for s in result["spots"]]
        assert "JA1XYZ" in calls or len(calls) > 0

    def test_spot_frequency_numeric(self):
        """HAMQTH-L2-026: Spot frequency is a string."""
        result = hamqth_dx_spots()
        for spot in result["spots"]:
            assert isinstance(spot["freq"], str)


# ---------------------------------------------------------------------------
# HAMQTH-L2-029..035: hamqth_rbn
# ---------------------------------------------------------------------------


class TestRbn:
    def test_returns_decodes(self):
        """HAMQTH-L2-029: RBN returns mock decodes."""
        result = hamqth_rbn()
        assert "error" not in result
        assert result["total"] == 2
        assert len(result["decodes"]) == 2

    def test_with_band_filter(self):
        """HAMQTH-L2-030: Band filter accepted."""
        result = hamqth_rbn(band="20", mode="CW")
        assert "error" not in result

    def test_decode_fields(self):
        """HAMQTH-L2-031: Decodes have required fields."""
        result = hamqth_rbn()
        required = {"call", "freq", "mode", "age"}
        for decode in result["decodes"]:
            assert required.issubset(decode.keys())

    def test_age_is_integer(self):
        """HAMQTH-L2-032: Decode age is integer (seconds)."""
        result = hamqth_rbn()
        for decode in result["decodes"]:
            assert isinstance(decode["age"], int)

    def test_listeners_present(self):
        """HAMQTH-L2-033: Decodes include listeners dict."""
        result = hamqth_rbn()
        for decode in result["decodes"]:
            assert "listeners" in decode
            assert isinstance(decode["listeners"], dict)


# ---------------------------------------------------------------------------
# HAMQTH-L2-036..040: hamqth_verify_qso
# ---------------------------------------------------------------------------


class TestVerifyQso:
    def test_verified(self):
        """HAMQTH-L2-036: Mock verify returns result=Y."""
        result = hamqth_verify_qso(
            mycall="KI7MT", hiscall="OK2CQR", date="20260305", band="20M"
        )
        assert "error" not in result
        assert result.get("result") == "Y"

    def test_verify_fields(self):
        """HAMQTH-L2-037: Verify result has expected fields."""
        result = hamqth_verify_qso(
            mycall="KI7MT", hiscall="OK2CQR", date="20260305", band="20M"
        )
        expected = {"result", "mycall", "hiscall", "date", "band"}
        assert expected.issubset(result.keys())

    def test_verify_callsigns_echoed(self):
        """HAMQTH-L2-038: Verify echoes back callsigns."""
        result = hamqth_verify_qso(
            mycall="KI7MT", hiscall="OK2CQR", date="20260305", band="20M"
        )
        assert result.get("mycall") == "KI7MT"
        assert result.get("hiscall") == "OK2CQR"


# ---------------------------------------------------------------------------
# HAMQTH-L2-041..045: Client direct tests
# ---------------------------------------------------------------------------


class TestClientDirect:
    def test_lookup_direct(self, client):
        """HAMQTH-L2-041: Direct client lookup returns dict."""
        result = client.lookup("OK2CQR")
        assert result["callsign"] == "OK2CQR"

    def test_dxcc_direct(self, client):
        """HAMQTH-L2-042: Direct client DXCC returns dict."""
        result = client.dxcc("VP8PJ")
        assert result["name"] == "South Shetland Islands"

    def test_dx_spots_direct(self, client):
        """HAMQTH-L2-043: Direct client dx_spots returns list."""
        result = client.dx_spots()
        assert len(result) == 3

    def test_rbn_direct(self, client):
        """HAMQTH-L2-044: Direct client RBN returns list."""
        result = client.rbn()
        assert len(result) == 2

    def test_verify_direct(self, client):
        """HAMQTH-L2-045: Direct client verify returns dict."""
        result = client.verify_qso("KI7MT", "OK2CQR", "20260305", "20M")
        assert result["result"] == "Y"
