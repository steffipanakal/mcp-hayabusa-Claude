# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This project is an MCP (Model Context Protocol) server that wraps [Hayabusa](https://github.com/Yamato-Security/hayabusa) for EVTX (Windows Event Log) analysis. It exposes Hayabusa's detection capabilities as MCP tools so that an MCP client (e.g. Claude Code, Claude Desktop) can drive EVTX analysis conversationally.

### Goals

- Expose a `scan_evtx` tool that runs Hayabusa against EVTX files.
- Return results as structured JSON (not raw Hayabusa CLI output).
- Support filtering by severity level (e.g. `low`, `medium`, `high`, `critical`).
- Handle errors gracefully — invalid paths, missing Hayabusa binary, malformed EVTX files, and non-zero Hayabusa exit codes should all surface as clear, structured errors rather than crashing the server.

## Stack

- **Language**: Python
- **MCP framework**: the `mcp` library (official Python SDK for the Model Context Protocol)
- **Analysis engine**: Hayabusa CLI, installed locally (invoked as a subprocess — not a Python binding)

## Architecture notes

- The server is a thin wrapper: it shells out to the locally installed Hayabusa CLI binary and translates its output into structured JSON for MCP tool responses, rather than reimplementing detection logic in Python.
- Since Hayabusa is invoked as a subprocess, argument construction and output parsing (Hayabusa supports JSON output natively via CLI flags) are the two areas most likely to need care as this grows.
- Severity filtering should be treated as a first-class parameter on the `scan_evtx` tool input schema, not a post-processing step, where possible (i.e. prefer passing severity filters directly to Hayabusa's CLI flags over filtering results in Python) — check Hayabusa's CLI `--help` for the current flag names before implementing.

## Status

This repository is in early/pre-implementation stage. No source files, dependency manifests, or tests exist yet. Update this file's Commands and Architecture sections once the project structure (entry point, tool definitions, packaging) is in place.
