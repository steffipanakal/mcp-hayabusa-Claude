"""MCP server that wraps Hayabusa for EVTX analysis."""

import json
import platform
import subprocess
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

server = FastMCP("hayabusa")

HAYABUSA_DIR = Path(__file__).resolve().parent / "hayabusa"
HAYABUSA_BIN_NAME = "hayabusa.exe" if platform.system() == "Windows" else "hayabusa"
SCAN_TIMEOUT_SECONDS = 600

# Hayabusa's --min-level flag takes full words, but its JSON "Level" field is
# abbreviated by default (info/low/med/high/crit) - both spellings must map to
# the same rank so a caller can pass either.
SEVERITY_RANK = {
    "informational": 0,
    "info": 0,
    "low": 1,
    "medium": 2,
    "med": 2,
    "high": 3,
    "critical": 4,
    "crit": 4,
}
SEVERITY_CANONICAL = {0: "informational", 1: "low", 2: "medium", 3: "high", 4: "critical"}


def _resolve_hayabusa_binary() -> Path:
    exact = HAYABUSA_DIR / HAYABUSA_BIN_NAME
    if exact.is_file():
        return exact

    # Release archives ship version-suffixed binaries, e.g. hayabusa-3.10.0-win-x64.exe
    pattern = "hayabusa*.exe" if platform.system() == "Windows" else "hayabusa*"
    candidates = sorted(p for p in HAYABUSA_DIR.glob(pattern) if p.is_file())
    if candidates:
        return candidates[0]

    raise RuntimeError(
        f"Hayabusa binary not found in {HAYABUSA_DIR}. "
        "Run scripts/download_hayabusa.py to install it."
    )


def _normalize_min_severity(value: str) -> tuple[str, int]:
    rank = SEVERITY_RANK.get(value.strip().lower())
    if rank is None:
        valid = ", ".join(SEVERITY_CANONICAL[r] for r in sorted(SEVERITY_CANONICAL))
        raise ValueError(f"Invalid min_severity '{value}'. Must be one of: {valid}")
    return SEVERITY_CANONICAL[rank], rank


@server.tool()
def scan_evtx(evtx_path: str, min_severity: str | None = None) -> dict:
    """Scan an EVTX file with Hayabusa and return findings as structured JSON.

    Args:
        evtx_path: Path to the .evtx file to scan.
        min_severity: Optional minimum severity to include (informational, low, medium, high, critical).
    """
    path = Path(evtx_path)
    if not path.is_file():
        raise FileNotFoundError(f"EVTX file not found: {evtx_path}")
    path = path.resolve()  # subprocess runs with cwd=hayabusa dir, so relative paths must be made absolute first

    binary = _resolve_hayabusa_binary()

    min_rank = 0
    min_severity_canonical = None
    if min_severity is not None:
        min_severity_canonical, min_rank = _normalize_min_severity(min_severity)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        output_path = tmp_path / "results.jsonl"
        command = [
            str(binary),
            "json-timeline",
            "-f", str(path),
            "-o", str(output_path),
            "-L",  # JSONL output, one finding per line
            "-w",  # no interactive wizard
            "-q",  # quiet banner
            "-K",  # no ANSI color codes
            "-N",  # skip results summary
            "-r", str(binary.parent / "rules"),
            "-c", str(binary.parent / "rules" / "config"),
        ]
        if min_severity_canonical is not None:
            command += ["-m", min_severity_canonical]

        try:
            result = subprocess.run(
                command,
                cwd=tmp_path,  # keeps each scan's error logs isolated instead of littering the install dir
                capture_output=True,
                text=True,
                timeout=SCAN_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Hayabusa scan timed out after {SCAN_TIMEOUT_SECONDS} seconds") from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to execute Hayabusa: {exc}") from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"Hayabusa exited with status {result.returncode}: {result.stderr.strip()}"
            )

        # Hayabusa exits 0 even when it fails to parse a file (e.g. a corrupt or
        # non-EVTX input) - it only reports this via an error log, not stdout/stderr
        # or the exit code, so that log is the one reliable signal of a scan failure.
        error_log_dir = tmp_path / "logs"
        if error_log_dir.is_dir():
            log_contents = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in error_log_dir.glob("*.log"))
            if log_contents.strip():
                raise RuntimeError(f"Hayabusa reported a scan error: {log_contents.strip()}")

        findings = []
        if output_path.exists():
            with open(output_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    if SEVERITY_RANK.get(str(record.get("Level", "")).lower(), -1) >= min_rank:
                        findings.append(record)

    return {
        "evtx_path": str(path),
        "min_severity": min_severity_canonical,
        "finding_count": len(findings),
        "findings": findings,
    }


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
