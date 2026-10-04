<!-- mcp-name: io.github.qso-graph/hamqth-mcp -->
# hamqth-mcp

[![PyPI](https://img.shields.io/pypi/v/hamqth-mcp?label=PyPI&color=blue)](https://pypi.org/project/hamqth-mcp/)
[![MCP Registry](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fregistry.modelcontextprotocol.io%2Fv0%2Fservers%3Fsearch%3Dio.github.qso-graph%2Fhamqth-mcp%26version%3Dlatest&query=%24.servers%5B0%5D.server.version&label=MCP%20Registry&color=blue)](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.qso-graph/hamqth-mcp&version=latest)

MCP server for [HamQTH.com](https://www.hamqth.com/) — callsign lookup, DX cluster spots, Reverse Beacon Network, DXCC resolution, and more through any MCP-compatible AI assistant.

Part of the [qso-graph](https://qso-graph.io/) project. Authenticated tools use [qso-graph-auth](https://pypi.org/project/qso-graph-auth/) for persona and credential management.

## Install

```bash
uvx hamqth-mcp            # run it; nothing to install
```

## Tools

| Tool | Auth | Description |
|------|------|-------------|
| `hamqth_lookup` | Yes | Callsign lookup (name, grid, DXCC, coordinates, QSL preferences) |
| `hamqth_dxcc` | No | Resolve DXCC entity from callsign or ADIF code |
| `hamqth_bio` | Yes | Fetch operator biography |
| `hamqth_activity` | Yes | Recent DX cluster, RBN, and logbook activity |
| `hamqth_dx_spots` | No | Live DX cluster spots — filter by band and/or callsign |
| `hamqth_rbn` | No | Reverse Beacon Network decodes — filter by band, mode, continent, callsign |
| `hamqth_verify_qso` | No | Verify a QSO via HamQTH SAVP protocol |
| `get_version_info` | No | Service version + upstream HamQTH API version (fleet identity attestation) |

## Quick Start

### 1. Create a free HamQTH account

Sign up at [hamqth.com](https://www.hamqth.com/) — it's free, no subscription required.

### 2. Set up credentials

hamqth-mcp uses [qso-graph-auth](https://qso-graph.io/servers/qso-graph-auth/) personas for credential management:

```bash
# Install qso-graph-auth if you haven't
uv tool install qso-graph-auth

# A persona (your callsign and the dates it covers), then HamQTH for it
qso-auth persona add --name ki7mt --callsign KI7MT --start 2020-01-01
qso-auth provider enable ki7mt hamqth
qso-auth creds set ki7mt hamqth      # asks for your username, then your password (hidden)
```

All three steps are needed: without `provider enable`, the server reports that the persona has no `hamqth` ref.

### 3. Configure your MCP client

hamqth-mcp works with any MCP-compatible client. Add the server config and restart — tools appear automatically.

#### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "hamqth": {
      "command": "uvx",
      "args": ["hamqth-mcp"]
    }
  }
}
```

#### Claude Code

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "hamqth": {
      "command": "uvx",
      "args": ["hamqth-mcp"]
    }
  }
}
```

#### ChatGPT Desktop

```json
{
  "mcpServers": {
    "hamqth": {
      "command": "uvx",
      "args": ["hamqth-mcp"]
    }
  }
}
```

#### Cursor

Add to `.cursor/mcp.json` (project-level) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "hamqth": {
      "command": "uvx",
      "args": ["hamqth-mcp"]
    }
  }
}
```

#### VS Code / GitHub Copilot

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "hamqth": {
      "command": "uvx",
      "args": ["hamqth-mcp"]
    }
  }
}
```

#### Gemini CLI

Add to `~/.gemini/settings.json` (global) or `.gemini/settings.json` (project):

```json
{
  "mcpServers": {
    "hamqth": {
      "command": "uvx",
      "args": ["hamqth-mcp"]
    }
  }
}
```

### 4. Ask questions

> "Look up the callsign OK2CQR"

> "What DXCC entity is VP8PJ?"

> "Show me the biography for OK2CQR"

> "What's the recent activity for KI7MT?"

> "Show me DX spots for 3Y0K"

> "What RBN decodes are there for 3Y0K on CW?"

> "Show me 20m DX spots"

> "Verify my QSO with OK2CQR on 20m on March 5"

## Testing Without Credentials

The DXCC tool (`hamqth_dxcc`) works without any credentials — it uses a public endpoint.

For testing all tools without a HamQTH account:

```bash
HAMQTH_MCP_MOCK=1 hamqth-mcp
```

## MCP Inspector

```bash
hamqth-mcp --transport streamable-http --port 8005
```

Then open the MCP Inspector at `http://localhost:8005`.

## Development

```bash
git clone https://github.com/qso-graph/hamqth-mcp.git
cd hamqth-mcp
uv sync --group dev
uv run pytest
```

## Known Quirks

- **Sessions:** HamQTH's XML sessions expire after an hour. The server signs in again after 55 minutes, so a long-running session never sees an expired one.

## License

GPL-3.0-or-later
