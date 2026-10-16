"""Conservative, opt-in installation into local client settings."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import tomllib
from pathlib import Path

from .auth import MusicError
from .clients import CLIENTS, absolute_path, add_connection_options, entry_from_args, render_config

PROJECT_CONFIGS = {
    "claude-code": ".mcp.json",
    "codex": ".codex/config.toml",
    "gemini-cli": ".gemini/settings.json",
    "cursor": ".cursor/mcp.json",
    "vscode": ".vscode/mcp.json",
}


def application_data() -> Path:
    defaults = {
        "darwin": Path.home() / "Library/Application Support",
        "win32": Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")),
    }
    return defaults.get(
        sys.platform, Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    )


def user_config(client: str) -> Path:
    if client == "claude-desktop" and sys.platform not in {"darwin", "win32"}:
        raise MusicError("Specify --config-file for Claude Desktop on this operating system.")
    locations = {
        "claude-code": Path.home() / ".claude.json",
        "claude-desktop": application_data() / "Claude/claude_desktop_config.json",
        "codex": Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml",
        "gemini-cli": Path.home() / ".gemini/settings.json",
        "cursor": Path.home() / ".cursor/mcp.json",
        "vscode": application_data() / "Code/User/mcp.json",
    }
    try:
        return absolute_path(locations[client])
    except KeyError:
        raise MusicError("Specify --config-file for a generic MCP client.") from None


def project_config(client: str, project: Path) -> Path:
    try:
        return absolute_path(project) / PROJECT_CONFIGS[client]
    except KeyError:
        raise MusicError("This client has no project configuration; use --config-file.") from None


def target_path(args) -> Path:
    if args.config_file is not None:
        return absolute_path(args.config_file)
    if args.scope == "project":
        return project_config(args.client, args.project_dir)
    return user_config(args.client)


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def parse_config(client: str, contents: bytes) -> dict:
    try:
        text = contents.decode("utf-8-sig")
        parsers = {
            "toml": tomllib.loads,
            "json": lambda value: json.loads(value, object_pairs_hook=unique_object),
        }
        parsed = parsers[CLIENTS[client].format](text) if text.strip() else {}
    except (ValueError, UnicodeError):
        raise MusicError(
            "Cannot parse client settings. JSON comments, trailing commas, and duplicate keys "
            "are not supported by this installer. Use the config command to merge manually."
        ) from None
    if not isinstance(parsed, dict):
        raise MusicError("Client settings must be an object or TOML document.")
    return parsed


def server_table(settings: dict, client: str) -> dict:
    servers = settings.setdefault(CLIENTS[client].root_key, {})
    if not isinstance(servers, dict):
        raise MusicError("The client MCP server section must be an object or TOML table.")
    return servers


def merge_config(client: str, name: str, entry: dict, original: bytes | None) -> bytes:
    original_bytes = original or b""
    settings = parse_config(client, original_bytes)
    servers = server_table(settings, client)
    if servers.get(name) == entry:
        return original_bytes
    if name in servers:
        raise MusicError(
            "That server name already has different settings. Use --name for another entry, "
            "or edit/remove the existing entry in your client before reinstalling."
        )
    servers[name] = entry
    return merged_bytes(client, name, entry, settings, original_bytes)


def merged_bytes(client: str, name: str, entry: dict, settings: dict, original: bytes) -> bytes:
    if CLIENTS[client].format == "toml":
        # Append rather than reserialize: preserve all unrelated TOML and comments.
        candidate = original + b"\n\n" + render_config(client, name, entry).encode()
        parse_config(client, candidate)  # Inline/sealed tables cannot always be extended.
        return candidate
    return (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode()


def read_existing(target: Path) -> bytes | None:
    if target.is_symlink():
        raise MusicError("Settings are a symbolic link. Pass the real file with --config-file.")
    try:
        return target.read_bytes()
    except FileNotFoundError:
        return None


def private_temp(target: Path, contents: bytes, suffix: str) -> Path:
    fd, filename = tempfile.mkstemp(prefix=target.name + suffix, dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        Path(filename).unlink(missing_ok=True)
        raise
    return Path(filename)


def write_config(target: Path, original: bytes | None, updated: bytes) -> Path | None:
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = private_temp(target, updated, ".tmp-")
    try:
        if read_existing(target) != original:
            raise MusicError("Client settings changed during setup. Run the installer again.")
        backup = private_temp(target, original, ".backup-") if original is not None else None
        os.replace(temporary, target)
        return backup
    finally:
        temporary.unlink(missing_ok=True)


def install_config(args) -> dict:
    target = target_path(args)
    entry = entry_from_args(args)
    original = read_existing(target)
    updated = merge_config(args.client, args.name, entry, original)
    result = {"client": args.client, "config_file": str(target), "server": args.name}
    if original == updated:
        return {**result, "status": "already_configured"}
    if args.dry_run:
        return {**result, "status": "preview", "entry": entry}
    backup = write_config(target, original, updated)
    return {
        **result,
        "status": "installed",
        "backup": str(backup) if backup else None,
        "next": "Reload the client's MCP connections and approve the server when prompted.",
    }


def install_client(args) -> None:
    try:
        result = install_config(args)
    except OSError:
        raise MusicError(
            "Cannot access client settings. Check the path and file permissions."
        ) from None
    print(json.dumps(result, indent=2))


def add_install_command(commands) -> None:
    parser = commands.add_parser("install", help="Add the server to a local client's settings")
    add_connection_options(parser)
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--config-file", type=Path, help="Override the client settings path")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changing settings")
