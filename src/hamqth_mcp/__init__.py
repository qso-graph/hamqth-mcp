"""MCP server for HamQTH.com — callsign lookup (free QRZ alternative)"""

from __future__ import annotations

try:
    from importlib.metadata import version

    __version__ = version("hamqth-mcp")
except Exception:
    __version__ = "0.0.0-dev"
