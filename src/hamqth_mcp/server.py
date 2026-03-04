"""hamqth-mcp: MCP server for HamQTH.com — free callsign lookup."""

from __future__ import annotations

import os
import sys
from typing import Any

from fastmcp import FastMCP

from adif_mcp.credentials import get_creds

from . import __version__
from .client import HamQTHClient

mcp = FastMCP(
    "hamqth-mcp",
    version=__version__,
    instructions=(
        "MCP server for HamQTH.com — free callsign lookup, DXCC resolution, "
        "biography, and recent activity. No paid subscription required."
    ),
)

_clients: dict[str, HamQTHClient] = {}
_public_client: HamQTHClient | None = None


def _is_mock() -> bool:
    return os.getenv("HAMQTH_MCP_MOCK") == "1"


def _client(persona: str) -> HamQTHClient:
    """Get or create an authenticated client for a persona."""
    if persona not in _clients:
        client = HamQTHClient()
        if not _is_mock():
            creds = get_creds(persona, "hamqth")
            if creds is None or not creds.username or not creds.password:
                raise ValueError(
                    f"No HamQTH credentials for persona '{persona}'. "
                    "Set up with: adif-mcp creds set --persona <name> --provider hamqth "
                    "--username <call> --password <pass>"
                )
            client.configure(creds.username, creds.password)
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
