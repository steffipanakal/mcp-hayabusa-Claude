#!/usr/bin/env python3
"""Download the latest Hayabusa release for this platform and extract it to ./hayabusa/."""

import json
import os
import platform
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

REPO = "Yamato-Security/hayabusa"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
DEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hayabusa")

# Substrings excluded from every match: the live-response bundles are a
# different tool variant, and all-platforms is a multi-OS archive we never want.
EXCLUDED_SUBSTRINGS = ("live-response", "all-platforms")


def detect_os_key() -> str:
    system = platform.system()
    if system == "Windows":
        return "win"
    if system == "Linux":
        return "lin"
    if system == "Darwin":
        return "mac"
    raise RuntimeError(f"Unsupported operating system: {system}")


def detect_arch_key() -> str:
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "x64"
    if machine in ("arm64", "aarch64"):
        return "aarch64"
    if machine in ("x86", "i386", "i686"):
        return "x86"
    raise RuntimeError(f"Unsupported architecture: {machine}")


def github_get(url: str) -> dict:
    headers = {
        "User-Agent": "mcp-hayabusa-installer",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API request failed ({exc.code}): {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach GitHub API: {exc.reason}") from exc


def pick_asset(assets: list, os_key: str, arch_key: str) -> dict:
    candidates = [
        asset
        for asset in assets
        if os_key in asset["name"]
        and arch_key in asset["name"]
        and not any(excluded in asset["name"] for excluded in EXCLUDED_SUBSTRINGS)
    ]
    if not candidates:
        available = ", ".join(asset["name"] for asset in assets)
        raise RuntimeError(
            f"No release asset found matching os='{os_key}' arch='{arch_key}'. "
            f"Available assets: {available}"
        )

    # Linux ships both glibc and musl builds; prefer glibc unless told otherwise.
    if os_key == "lin" and len(candidates) > 1:
        gnu_build = next((a for a in candidates if "gnu" in a["name"]), None)
        if gnu_build:
            return gnu_build

    return candidates[0]


def download_asset(asset: dict, dest_path: str) -> None:
    request = urllib.request.Request(
        asset["browser_download_url"],
        headers={"User-Agent": "mcp-hayabusa-installer"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, open(dest_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Download failed ({exc.code}): {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Download failed: {exc.reason}") from exc


def extract_zip(zip_path: str, dest_dir: str) -> None:
    os.makedirs(dest_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(dest_dir)
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"Downloaded file is not a valid zip archive: {exc}") from exc


def make_binaries_executable(dest_dir: str) -> None:
    if platform.system() == "Windows":
        return
    for name in os.listdir(dest_dir):
        if name.startswith("hayabusa"):
            path = os.path.join(dest_dir, name)
            current_mode = os.stat(path).st_mode
            os.chmod(path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    try:
        os_key = detect_os_key()
        arch_key = detect_arch_key()

        print(f"Detected platform: os='{os_key}' arch='{arch_key}'")
        print(f"Fetching latest release info from {API_URL} ...")
        release = github_get(API_URL)
        tag_name = release.get("tag_name", "unknown")
        assets = release.get("assets", [])
        if not assets:
            raise RuntimeError("Latest release has no downloadable assets.")

        asset = pick_asset(assets, os_key, arch_key)
        print(f"Selected {asset['name']} from release {tag_name}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = os.path.join(tmp_dir, asset["name"])
            print("Downloading ...")
            download_asset(asset, archive_path)

            print(f"Extracting to {DEST_DIR} ...")
            extract_zip(archive_path, DEST_DIR)

        make_binaries_executable(DEST_DIR)
        print(f"Done. Hayabusa {tag_name} is available in {DEST_DIR}")
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
