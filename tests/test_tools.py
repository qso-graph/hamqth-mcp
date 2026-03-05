"""Mock-mode tests for all 7 hamqth-mcp tools."""

import os

os.environ["HAMQTH_MCP_MOCK"] = "1"

from hamqth_mcp.server import (  # noqa: E402
    hamqth_activity,
    hamqth_bio,
    hamqth_dxcc,
    hamqth_dx_spots,
    hamqth_lookup,
    hamqth_rbn,
    hamqth_verify_qso,
)


# -- Existing tools ----------------------------------------------------------


def test_lookup_mock():
    result = hamqth_lookup(persona="test", callsign="OK2CQR")
    assert "error" not in result
    assert result["callsign"] == "OK2CQR"
    assert result["country"] == "Czech Republic"


def test_dxcc_mock():
    result = hamqth_dxcc(query="VP8PJ")
    assert "error" not in result
    assert result["name"] == "South Shetland Islands"
    assert result["dxcc"] == 241


def test_bio_mock():
    result = hamqth_bio(persona="test", callsign="OK2CQR")
    assert result["callsign"] == "OK2CQR"
    assert result["bio"] is not None
    assert "HamQTH" in result["bio"]


def test_activity_mock():
    result = hamqth_activity(persona="test", callsign="KI7MT")
    assert result["callsign"] == "KI7MT"
    assert result["total"] >= 1
    assert len(result["activity"]) >= 1


# -- DX Spots ----------------------------------------------------------------


def test_dx_spots_default():
    result = hamqth_dx_spots()
    assert "error" not in result
    assert result["total"] == 3
    assert len(result["spots"]) == 3


def test_dx_spots_with_band():
    result = hamqth_dx_spots(limit=60, band="20M")
    assert "error" not in result
    assert isinstance(result["spots"], list)


def test_dx_spots_fields():
    result = hamqth_dx_spots()
    required = {"call", "freq", "datetime", "spotter", "band", "country"}
    for spot in result["spots"]:
        assert required.issubset(spot.keys()), f"Missing fields: {required - spot.keys()}"


# -- RBN ---------------------------------------------------------------------


def test_rbn_default():
    result = hamqth_rbn()
    assert "error" not in result
    assert result["total"] == 2
    assert len(result["decodes"]) == 2


def test_rbn_with_filters():
    result = hamqth_rbn(band="20", mode="CW")
    assert "error" not in result
    assert isinstance(result["decodes"], list)


def test_rbn_fields():
    result = hamqth_rbn()
    required = {"call", "freq", "mode", "age"}
    for decode in result["decodes"]:
        assert required.issubset(decode.keys()), f"Missing fields: {required - decode.keys()}"
        assert isinstance(decode["age"], int)


# -- Verify QSO --------------------------------------------------------------


def test_verify_qso():
    result = hamqth_verify_qso(
        mycall="KI7MT", hiscall="OK2CQR", date="20260305", band="20M"
    )
    assert "error" not in result
    assert result.get("result") == "Y"


def test_verify_qso_fields():
    result = hamqth_verify_qso(
        mycall="KI7MT", hiscall="OK2CQR", date="20260305", band="20M"
    )
    expected = {"result", "mycall", "hiscall", "date", "band"}
    assert expected.issubset(result.keys()), f"Missing fields: {expected - result.keys()}"
