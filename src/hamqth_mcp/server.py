"""hamqth-mcp: MCP server for HamQTH.com — callsign lookup, DX spots, RBN, QSO verification."""

from __future__ import annotations

import os
import sys
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from qso_graph_auth.identity import PersonaManager

from . import __spec_version__, __version__
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

# MCP 2026-07-28 tool annotations. The defaults are pessimistic — a tool that
# declares nothing is advertised as destructive, non-idempotent and open-world,
# and the specification tells a client to keep a human in the loop for an
# operation like that. So a client would be entitled to put a confirmation
# prompt in front of looking up a callsign. Every tool here reads and none
# writes, so the three effect hints are the same for all of them.
#
# openWorldHint is true for the seven that reach hamqth.com — three of them
# with the operator's credentials, four on public endpoints — and false only
# for get_version_info, which reports what the wheel carries.
#
# They are a client's UX hint and never a security control: the specification
# requires clients to treat them as untrusted. In particular, nothing here
# tells a client that three of these tools use a stored credential; that is not
# what annotations are for, and it is not a substitute for the keyring.
_READS_HAMQTH = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
_ANSWERS_FROM_THE_PACKAGE = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    # Reports versions carried in the wheel. It opens no connection and reads
    # no credential.
    "openWorldHint": False,
}




def _version_info_payload() -> dict[str, Any]:
    """Build the version info envelope. Pulled into a helper so tests can
    call it directly without going through the FastMCP wrapper."""
    return {
        "service_name": "hamqth-mcp",
        "service_version": __version__,
        "spec_version": __spec_version__,
    }


@mcp.tool(annotations=_ANSWERS_FROM_THE_PACKAGE)
def get_version_info() -> dict[str, Any]:
    """Get hamqth-mcp service version and upstream HamQTH API version.

    Returns the running PyPI version of hamqth-mcp and the HamQTH.com API
    contract in use. Use this to confirm fleet alignment across MCP
    deployments — agents can compare service_version and spec_version
    across servers to detect drift without going outside the MCP protocol.

    Returns:
        service_name, service_version (PyPI), and spec_version (HamQTH API).
    """
    return _version_info_payload()


@mcp.tool(annotations=_READS_HAMQTH)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_HAMQTH)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_HAMQTH)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_HAMQTH)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_HAMQTH)
def hamqth_dx_spots(
    limit: int = 60,
    band: str | None = None,
    call: str | None = None,
) -> dict[str, Any]:
    """Live DX cluster spots from HamQTH (public, no auth required).

    Spots update every ~15 seconds. Max 200 spots per request.

    Args:
        limit: Number of spots to return (default 60, max 200).
        band: Optional ADIF band filter (e.g., "20M", "40M").
        call: Optional callsign filter — matches spotted call or spotter
              (case-insensitive, e.g., "3Y0K"). Pulls max spots and filters
              client-side since the API does not support server-side filtering.

    Returns:
        List of DX cluster spots with call, freq, band, spotter, etc.
    """
    try:
        fetch_limit = 200 if call else limit
        spots = _public().dx_spots(limit=fetch_limit, band=band)
        if call:
            call_upper = call.upper()
            spots = [
                s for s in spots
                if call_upper in s.get("call", "").upper()
                or call_upper in s.get("spotter", "").upper()
            ]
        return {"total": len(spots), "spots": spots}
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_HAMQTH)
def hamqth_rbn(
    band: str | None = None,
    mode: str | None = None,
    cont: str | None = None,
    fromcont: str | None = None,
    age: int | None = None,
    call: str | None = None,
) -> dict[str, Any]:
    """Reverse Beacon Network spots from HamQTH (public, no auth required).

    Args:
        band: ADIF band numbers, comma-separated (e.g., "20,40").
        mode: Filter by mode (CW, RTTY, PSK31, PSK63).
        cont: Filter by spotted station's continent (e.g., "EU", "NA").
        fromcont: Filter by receiver/skimmer continent.
        age: Maximum age in seconds.
        call: Optional callsign filter — matches spotted station
              (case-insensitive, e.g., "3Y0K"). Filtered client-side.

    Returns:
        List of RBN decodes with call, freq, mode, age, and listener dB values.
    """
    try:
        decodes = _public().rbn(
            band=band, mode=mode, cont=cont, fromcont=fromcont, age=age
        )
        if call:
            call_upper = call.upper()
            decodes = [
                d for d in decodes
                if call_upper in d.get("call", "").upper()
            ]
        return {"total": len(decodes), "decodes": decodes}
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_HAMQTH)
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
        raise ToolError(str(e)) from e


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


USAGE = """\
usage: hamqth-mcp [--transport stdio|streamable-http] [--port N] [--version] [--help]

An MCP server: an AI app (Claude Desktop, Claude Code, ...) starts it and talks
to it over stdio. Run on its own it waits for that app; press Ctrl-C to stop.
Set up a client: https://github.com/qso-graph/hamqth-mcp#quick-start

streamable-http binds 127.0.0.1 only: not another machine,
not a container.
"""


def main() -> None:
    """Run the hamqth-mcp server."""
    # Without this the script ignored both flags and bound stdio, so
    # `--help` left a user watching a banner and a hung terminal.
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(USAGE, end="")
        return
    if "--version" in sys.argv[1:]:
        print(f"hamqth-mcp {__version__}")
        return
    transport = "stdio"
    port = 8005
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--transport" and i < len(sys.argv) - 1:
            transport = sys.argv[i + 1]
        if arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    # Written out rather than passed through: fastmcp takes a literal, and a
    # str that happens to hold the right word is not the same thing.
    if transport == "streamable-http":
        # Where it bound, said out loud. FastMCP binds 127.0.0.1 and takes
        # no host option, so this is never reachable from another machine
        # or from outside a container. Silent before this line.
        print(
            f"hamqth-mcp on http://127.0.0.1:{port}/mcp - loopback only",
            file=sys.stderr,
        )
        mcp.run(transport="streamable-http", port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
