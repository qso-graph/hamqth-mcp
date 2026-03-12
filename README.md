<!-- mcp-name: io.github.qso-graph/hamqth-mcp -->
# hamqth-mcp

MCP server for [HamQTH.com](https://www.hamqth.com/) — callsign lookup, DX cluster spots, Reverse Beacon Network, DXCC resolution, and more through any MCP-compatible AI assistant.

Part of the [qso-graph](https://qso-graph.io/) project. Authenticated tools use [qso-graph-auth](https://pypi.org/project/qso-graph-auth/) for persona and credential management.

## Install

```bash
pip install hamqth-mcp
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

## Quick Start

### 1. Create a free HamQTH account

Sign up at [hamqth.com](https://www.hamqth.com/) — it's free, no subscription required.

### 2. Set up credentials

hamqth-mcp uses adif-mcp personas for credential management:

```bash
# Install adif-mcp if you haven't
pip install adif-mcp

# Create a persona and add HamQTH credentials
adif-mcp persona create ki7mt --callsign KI7MT
adif-mcp persona provider ki7mt hamqth --username KI7MT
adif-mcp persona secret ki7mt hamqth
```

### 3. Configure your MCP client

hamqth-mcp works with any MCP-compatible client. Add the server config and restart — tools appear automatically.

#### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "hamqth": {
      "command": "hamqth-mcp"
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
      "command": "hamqth-mcp"
    }
  }
}
```

#### ChatGPT Desktop

```json
{
  "mcpServers": {
    "hamqth": {
      "command": "hamqth-mcp"
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
      "command": "hamqth-mcp"
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
      "command": "hamqth-mcp"
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
      "command": "hamqth-mcp"
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
pip install -e .
```

## License

GPL-3.0-or-later
