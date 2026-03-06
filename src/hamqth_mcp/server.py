"""hamqth-mcp: MCP server for HamQTH.com — callsign lookup, DX spots, RBN, QSO verification."""

from __future__ import annotations

import os
import sys
from typing import Any

from fastmcp import FastMCP

from adif_mcp.identity import PersonaManager

from . import __version__
from .client import HamQTHClient

mcp = FastMCP(
    "hamqth-mcp",
    version=__version__,
    instructions=(
        "MCP server for HamQTH.com — callsign lookup, DXCC resolution, "
        "DX cluster spots, RBN data, QSO verification, and more. "
        "Most endpoints are public (no auth). Lookup/bio/activity need a free account."
    ),
)

_clients: dict[str, HamQTHClient] = {}
_public_client: HamQTHClient | None = None


def _is_mock() -> bool:
    return os.getenv("HAMQTH_MCP_MOCK") == "1"


def _pm() -> PersonaManager:
    return PersonaManager()


def _client(persona: str) -> HamQTHClient:
    """Get or create an authenticated client for a persona."""
    if persona not in _clients:
        client = HamQTHClient()
        if not _is_mock():
            username, password = _pm().require(persona, "hamqth")
            client.configure(username, password)
        _clients[persona] = client
    return _clients[persona]


def _public() -> HamQTHClient:
    """Get or create a client for public (unauthenticated) endpoints."""
    global _public_client
    if _public_client is None:
        _public_client = HamQTHClient()
    return _public_client


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def hamqth_lookup(persona: str, callsign: str) -> dict[str, Any]:
    """Look up a callsign on HamQTH (free, no subscription required).

    Returns name, grid, DXCC, coordinates, QSL preferences, and more.
    Field availability depends on what the operator has published.

    Args:
        persona: Persona name configured in adif-mcp.
        callsign: Callsign to look up (e.g., OK2CQR).

    Returns:
        Structured record with station details.
    """
    try:
        return _client(persona).lookup(callsign)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def hamqth_dxcc(query: str) -> dict[str, Any]:
    """Resolve a DXCC entity from a callsign or ADIF entity code.

    Public endpoint — no authentication required.

    Args:
        query: Callsign (e.g., VP8PJ) or ADIF entity code (e.g., 291).

    Returns:
        DXCC entity details (name, continent, CQ/ITU zones, coordinates).
    """
    try:
        return _public().dxcc(query)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def hamqth_bio(persona: str, callsign: str) -> dict[str, Any]:
    """Fetch an operator's biography from HamQTH.

    Args:
        persona: Persona name configured in adif-mcp.
        callsign: Callsign to look up.

    Returns:
        Callsign and biography text (HTML stripped).
    """
    try:
        return _client(persona).bio(callsign)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def hamqth_activity(persona: str, callsign: str) -> dict[str, Any]:
    """Get recent DX cluster, RBN, and logbook activity for a callsign.

    Args:
        persona: Persona name configured in adif-mcp.
        callsign: Callsign to check.

    Returns:
        List of recent activity items (spots, RBN decodes, logbook entries).
    """
    try:
        return _client(persona).activity(callsign)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def hamqth_dx_spots(
    limit: int = 60, band: str | None = None
) -> dict[str, Any]:
    """Live DX cluster spots from HamQTH (public, no auth required).

    Spots update every ~15 seconds. Max 200 spots per request.

    Args:
        limit: Number of spots to return (default 60, max 200).
        band: Optional ADIF band filter (e.g., "20M", "40M").

    Returns:
        List of DX cluster spots with call, freq, band, spotter, etc.
    """
    try:
        spots = _public().dx_spots(limit=limit, band=band)
        return {"total": len(spots), "spots": spots}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def hamqth_rbn(
    band: str | None = None,
    mode: str | None = None,
    cont: str | None = None,
    fromcont: str | None = None,
    age: int | None = None,
) -> dict[str, Any]:
    """Reverse Beacon Network spots from HamQTH (public, no auth required).

    Args:
        band: ADIF band numbers, comma-separated (e.g., "20,40").
        mode: Filter by mode (CW, RTTY, PSK31, PSK63).
        cont: Filter by spotted station's continent (e.g., "EU", "NA").
        fromcont: Filter by receiver/skimmer continent.
        age: Maximum age in seconds.

    Returns:
        List of RBN decodes with call, freq, mode, age, and listener dB values.
    """
    try:
        decodes = _public().rbn(
            band=band, mode=mode, cont=cont, fromcont=fromcont, age=age
        )
        return {"total": len(decodes), "decodes": decodes}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def hamqth_verify_qso(
    mycall: str, hiscall: str, date: str, band: str
) -> dict[str, Any]:
    """Verify a QSO via HamQTH SAVP protocol (public, no auth required).

    Checks if a QSO exists in HamQTH's database for both parties.

    Args:
        mycall: Your callsign (e.g., "KI7MT").
        hiscall: Other station's callsign (e.g., "OK2CQR").
        date: QSO date in YYYYMMDD format (e.g., "20260305").
        band: Band (e.g., "20M", "40M").

    Returns:
        SAVP verification result with match status.
    """
    try:
        return _public().verify_qso(mycall, hiscall, date, band)
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the hamqth-mcp server."""
    transport = "stdio"
    port = 8005
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--transport" and i < len(sys.argv) - 1:
            transport = sys.argv[i + 1]
        if arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    if transport == "streamable-http":
        mcp.run(transport=transport, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
