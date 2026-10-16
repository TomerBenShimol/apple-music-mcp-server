"""Offline diagnostics and an optional read-only MCP discovery probe."""

from __future__ import annotations

import asyncio
import importlib.metadata
import importlib.util
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .auth import data_dir
from .clients import CLIENTS, absolute_path, server_entry


def dependency_version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def warnings(browser: bool) -> list[str]:
    result = []
    if not browser:
        result.append("Browser sign-in needs this package's [browser] extra and a browser runtime.")
    if sys.platform == "win32":
        result.append("Windows process locking is not implemented; avoid concurrent MCP clients.")
    return result


def diagnostics(credentials: Path) -> dict:
    directory = absolute_path(credentials)
    browser = importlib.util.find_spec("playwright") is not None
    dependencies = {name: dependency_version(name) for name in ("fastmcp", "httpx")}
    return {
        "status": "ready" if all(dependencies.values()) else "needs_attention",
        "version": __version__,
        "python": {"executable": sys.executable, "version": sys.version.split()[0]},
        "platform": sys.platform,
        "dependencies": dependencies,
        "browser_helper_installed": browser,
        "browser_runtime": "not_checked; sign-in needs Chrome on macOS or Playwright Chromium",
        "credential_directory": str(directory),
        "saved_credentials_present": (directory / "credentials.json").is_file(),
        "account_access": "not_checked; use status to verify with Apple",
        "native_backend_available": sys.platform == "darwin" and bool(shutil.which("osascript")),
        "native_automation_permission": "not_checked",
        "client_configuration_formats": list(CLIENTS),
        "warnings": warnings(browser),
    }


async def probe_server(credentials: Path) -> dict:
    from fastmcp import Client

    entry = server_entry("generic", Path(sys.executable), credentials, None)
    async with Client({"mcpServers": {"apple-music": entry}}, timeout=20) as client:
        discovered = await client.list_tools()
    names = sorted(tool.name for tool in discovered)
    required = {"get_status", "connect_apple_music", "search_music", "add_songs_to_library"}
    return {
        "status": "ready" if required.issubset(names) else "needs_attention",
        "transport": "stdio",
        "tool_count": len(names),
        "tools": names,
        "scope": "Local MCP discovery only; client applications and account access are not tested.",
    }


def run_probe(credentials: Path) -> dict:
    try:
        return asyncio.run(asyncio.wait_for(probe_server(credentials), timeout=30))
    except Exception as error:
        # Dependency/process failures may include configuration in their messages.
        return {"status": "needs_attention", "error_type": type(error).__name__}


def doctor(args) -> None:
    report = diagnostics(args.data_dir)
    if args.probe:
        report["mcp_probe"] = run_probe(args.data_dir)
        report["status"] = (
            "ready"
            if report["status"] == report["mcp_probe"]["status"] == "ready"
            else "needs_attention"
        )
    print(json.dumps(report, indent=2))
    if report["status"] != "ready":
        raise SystemExit(1)


def add_doctor_command(commands) -> None:
    parser = commands.add_parser("doctor", help="Check dependencies and optionally MCP discovery")
    parser.add_argument("--data-dir", type=Path, default=data_dir())
    parser.add_argument(
        "--probe", action="store_true", help="Start a temporary server and discover tools"
    )
