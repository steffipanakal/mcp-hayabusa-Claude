"""Standalone test script for server.scan_evtx.

Downloads a sample EVTX from the EVTX-ATTACK-SAMPLES repo (cached under
tests/fixtures/) and calls scan_evtx directly to exercise the happy path,
severity filtering, and error handling.
"""

import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "LM_WMIC_4648_rpcss.evtx"
FIXTURE_URL = (
    "https://raw.githubusercontent.com/sbousseaden/EVTX-ATTACK-SAMPLES/"
    "master/Lateral%20Movement/LM_WMIC_4648_rpcss.evtx"
)


def ensure_fixture() -> None:
    if FIXTURE_PATH.is_file():
        return
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading sample EVTX from {FIXTURE_URL} ...")
    try:
        urllib.request.urlretrieve(FIXTURE_URL, FIXTURE_PATH)
    except urllib.error.URLError as exc:
        print(f"FAIL: could not download sample EVTX fixture: {exc}")
        sys.exit(1)


def check(label: str, condition: bool) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")
    return condition


def main() -> int:
    ensure_fixture()
    ok = True

    result = server.scan_evtx(evtx_path=str(FIXTURE_PATH))
    ok &= check("scan returns at least one finding", result["finding_count"] > 0)
    ok &= check(
        "finding_count matches len(findings)",
        result["finding_count"] == len(result["findings"]),
    )
    unfiltered_count = result["finding_count"]

    filtered = server.scan_evtx(evtx_path=str(FIXTURE_PATH), min_severity="high")
    ok &= check("min_severity filter narrows results", filtered["finding_count"] <= unfiltered_count)
    ok &= check(
        "all filtered findings are 'high' or above",
        all(
            server.SEVERITY_RANK[f["Level"].lower()] >= server.SEVERITY_RANK["high"]
            for f in filtered["findings"]
        ),
    )

    try:
        server.scan_evtx(evtx_path="does_not_exist.evtx")
        ok &= check("missing EVTX file raises FileNotFoundError", False)
    except FileNotFoundError:
        ok &= check("missing EVTX file raises FileNotFoundError", True)

    try:
        server.scan_evtx(evtx_path=str(FIXTURE_PATH), min_severity="not_a_level")
        ok &= check("invalid min_severity raises ValueError", False)
    except ValueError:
        ok &= check("invalid min_severity raises ValueError", True)

    original_dir = server.HAYABUSA_DIR
    server.HAYABUSA_DIR = Path("does_not_exist_dir")
    try:
        server.scan_evtx(evtx_path=str(FIXTURE_PATH))
        ok &= check("missing Hayabusa binary raises RuntimeError", False)
    except RuntimeError:
        ok &= check("missing Hayabusa binary raises RuntimeError", True)
    finally:
        server.HAYABUSA_DIR = original_dir

    print()
    print("ALL PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
