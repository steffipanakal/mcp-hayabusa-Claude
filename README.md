# mcp-hayabusa

An MCP (Model Context Protocol) server that wraps [Hayabusa](https://github.com/Yamato-Security/hayabusa) for EVTX (Windows Event Log) analysis. It exposes Hayabusa's detection capabilities as an MCP tool so an MCP client (e.g. Claude Code, Claude Desktop) can drive EVTX analysis conversationally.

The server is a thin wrapper: it shells out to a locally installed Hayabusa CLI binary and translates its JSONL output into a structured MCP tool response, rather than reimplementing any detection logic in Python.

## Setup

### 1. Create a virtual environment and install dependencies

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 2. Download Hayabusa

The Hayabusa binary, detection rules, and config are not checked into this repo (see `.gitignore`) — they're downloaded release assets, not project source. Fetch them with:

```powershell
.venv\Scripts\python scripts\download_hayabusa.py
```

This detects your OS/architecture, pulls the latest release from `Yamato-Security/hayabusa`, and extracts it into `./hayabusa/` (binary, `rules/`, `config/`). Set a `GITHUB_TOKEN` environment variable first if you hit GitHub API rate limits.

### 3. Register the MCP server

`.mcp.json` is already configured to launch the server via the venv's Python:

```json
{
  "mcpServers": {
    "hayabusa": {
      "command": "C:********************.venv/Scripts/python.exe",
      "args": ["server.py"]
    }
  }
}
```

Update the `command` path if you cloned the repo elsewhere. Any MCP-compatible client (Claude Code, Claude Desktop) pointed at this config will pick up the `hayabusa` server automatically.

## Usage

Once connected, the server exposes one tool:

### `scan_evtx`

Scans an EVTX file with Hayabusa and returns findings as structured JSON.

| Argument | Type | Required | Description |
|---|---|---|---|
| `evtx_path` | string | yes | Path to the `.evtx` file to scan |
| `min_severity` | string | no | Minimum severity to include: `informational`, `low`, `medium`, `high`, `critical` |

Example response shape:

```json
{
  "evtx_path": "C:/logs/Security.evtx",
  "min_severity": "high",
  "finding_count": 3,
  "findings": [ { "...": "one JSON object per Hayabusa detection" } ]
}
```

Errors (missing file, invalid `min_severity`, missing Hayabusa binary, non-zero Hayabusa exit code, or a scan Hayabusa silently failed to parse) are raised as Python exceptions with a clear message rather than crashing the server.

From an MCP client, just ask conversationally, e.g.:

> Scan C:\logs\Security.evtx with Hayabusa and only show me high and critical findings.

## Testing

`tests/test_scan_evtx.py` is a standalone script (not pytest) that downloads a sample EVTX from the [EVTX-ATTACK-SAMPLES](https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES) repo on first run, caches it under `tests/fixtures/`, and exercises the happy path, severity filtering, and error handling:

```powershell
.venv\Scripts\python tests\test_scan_evtx.py
```

## Project layout

```
server.py                  # MCP server + scan_evtx tool
scripts/download_hayabusa.py  # Fetches the latest Hayabusa release into ./hayabusa/
hayabusa/                  # Downloaded binary, rules, config (gitignored)
tests/test_scan_evtx.py    # Standalone functional test
.mcp.json                  # MCP client registration
```
