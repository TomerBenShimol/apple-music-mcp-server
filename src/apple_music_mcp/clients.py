"""Local MCP client configuration, independent of any model provider."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .auth import MusicError, data_dir


@dataclass(frozen=True)
class ClientProfile:
    label: str
    root_key: str = "mcpServers"
    format: str = "json"
    explicit_type: bool = False


CLIENTS = {
    "claude-code": ClientProfile("Claude Code", explicit_type=True),
    "claude-desktop": ClientProfile("Claude Desktop"),
    "codex": ClientProfile("Codex", root_key="mcp_servers", format="toml"),
    "gemini-cli": ClientProfile("Gemini CLI"),
    "cursor": ClientProfile("Cursor"),
    "vscode": ClientProfile("VS Code", root_key="servers", explicit_type=True),
    "generic": ClientProfile("Other stdio MCP clients"),
}


def absolute_path(value: str | Path) -> Path:
    # Resolving symlinks would replace a virtualenv's Python with the system interpreter.
    return Path(os.path.abspath(Path(value).expanduser()))


def checked_name(name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", name):
        raise MusicError("Use a server name of 1–48 lowercase letters, digits, or hyphens.")
    return name


def checked_storefront(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z]{2}", value):
        raise MusicError("Use a two-letter Apple Music storefront, such as us or gb.")
    return value.lower()


def server_entry(client: str, python: Path, credentials: Path, storefront: str | None) -> dict:
    interpreter = absolute_path(python)
    if not interpreter.is_file():
        raise MusicError("The Python executable does not exist. Install the package first.")
    environment = {"APPLE_MUSIC_MCP_HOME": str(absolute_path(credentials))}
    if storefront is not None:
        environment["APPLE_MUSIC_STOREFRONT"] = checked_storefront(storefront)
    return {
        **({"type": "stdio"} if CLIENTS[client].explicit_type else {}),
        "command": str(interpreter),
        "args": ["-m", "apple_music_mcp", "serve"],
        "env": environment,
    }


def configuration(client: str, name: str, entry: dict) -> dict:
    return {CLIENTS[client].root_key: {checked_name(name): entry}}


def toml_config(name: str, entry: dict) -> str:
    table = f"mcp_servers.{json.dumps(checked_name(name))}"
    lines = [f"[{table}]", f"command = {json.dumps(entry['command'], ensure_ascii=False)}"]
    lines.append(f"args = {json.dumps(entry['args'])}")
    lines.extend(["", f"[{table}.env]"])
    lines.extend(
        f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in entry["env"].items()
    )
    return "\n".join(lines) + "\n"


def render_config(client: str, name: str, entry: dict) -> str:
    if CLIENTS[client].format == "toml":
        return toml_config(name, entry)
    return json.dumps(configuration(client, name, entry), indent=2) + "\n"


def add_connection_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("client", choices=CLIENTS)
    parser.add_argument("--name", default="apple-music", help="MCP server name")
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--data-dir", type=Path, default=data_dir(), help="Shared local credential directory"
    )
    parser.add_argument("--storefront", help="Optional two-letter catalog storefront")


def add_commands(commands) -> None:
    commands.add_parser("clients", help="List available local client configuration formats")
    parser = commands.add_parser("config", help="Print client configuration without changing files")
    add_connection_options(parser)


def entry_from_args(args) -> dict:
    checked_name(args.name)
    return server_entry(args.client, args.python, args.data_dir, args.storefront)


def show_config(args) -> None:
    print(render_config(args.client, args.name, entry_from_args(args)), end="")


def list_clients(_args) -> None:
    print(
        json.dumps(
            [
                {"id": name, "name": profile.label, "format": profile.format, "transport": "stdio"}
                for name, profile in CLIENTS.items()
            ],
            indent=2,
        )
    )
