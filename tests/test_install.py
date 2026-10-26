import json
import os
import sys
import tomllib
from pathlib import Path

import pytest

from apple_music_mcp.auth import MusicError
from apple_music_mcp.cli import build_parser
from apple_music_mcp.clients import CLIENTS
from apple_music_mcp.install import install_config, project_config, user_config, write_config


def arguments(tmp_path, client="cursor", *extra):
    return build_parser().parse_args(
        [
            "install",
            client,
            "--config-file",
            str(tmp_path / "client config"),
            "--data-dir",
            str(tmp_path / "music"),
            *extra,
        ]
    )


@pytest.mark.parametrize("client", CLIENTS)
def test_install_round_trip_preserves_unrelated_settings_and_is_idempotent(tmp_path, client):
    args = arguments(tmp_path, client)
    root = CLIENTS[client].root_key
    original = (
        b'# retain my comment\nmodel = "example"\n[mcp_servers.other]\ncommand = "other"\n'
        if client == "codex"
        else json.dumps({"unrelated": "keep", root: {"other": {"command": "other"}}}).encode()
    )
    args.config_file.write_bytes(original)
    first = install_config(args)
    assert Path(first["backup"]).read_bytes() == original
    contents = args.config_file.read_text()
    decoded = tomllib.loads(contents) if client == "codex" else json.loads(contents)
    assert decoded[root]["other"] == {"command": "other"}
    assert decoded[root]["apple-music"]["args"] == ["-m", "apple_music_mcp", "serve"]
    second = install_config(args)
    assert second["status"] == "already_configured"
    assert args.config_file.read_text() == contents
    assert len(list(tmp_path.glob("*.backup-*"))) == 1
    if client == "codex":
        assert contents.startswith(original.decode())


def test_install_preview_does_not_write_anything_or_print_existing_secrets(tmp_path):
    args = arguments(tmp_path, "cursor", "--dry-run")
    original = b'{"apiKey":"existing-secret","mcpServers":{}}'
    args.config_file.write_bytes(original)
    result = install_config(args)
    assert result["status"] == "preview"
    assert "existing-secret" not in json.dumps(result)
    assert args.config_file.read_bytes() == original
    assert list(tmp_path.iterdir()) == [args.config_file]


@pytest.mark.parametrize("client", CLIENTS)
def test_different_existing_entry_is_never_overwritten(tmp_path, client):
    args = arguments(tmp_path, client)
    original = (
        b'[mcp_servers.apple-music]\ncommand = "keep"'
        if client == "codex"
        else json.dumps({CLIENTS[client].root_key: {"apple-music": {"command": "keep"}}}).encode()
    )
    args.config_file.write_bytes(original)
    with pytest.raises(MusicError, match="already has different settings"):
        install_config(args)
    assert args.config_file.read_bytes() == original
    assert not list(tmp_path.glob("*.backup-*"))


@pytest.mark.parametrize(
    "contents",
    [
        b'{// comment\n"mcpServers": {}}',
        b'{"mcpServers":{},}',
        b'{"mcpServers":{},"mcpServers":{}}',
        b"[]",
        b'{"mcpServers": []}',
    ],
)
def test_unsupported_json_is_preserved(tmp_path, contents):
    args = arguments(tmp_path)
    args.config_file.write_bytes(contents)
    with pytest.raises(MusicError):
        install_config(args)
    assert args.config_file.read_bytes() == contents


def test_sealed_toml_table_is_preserved_when_it_cannot_be_extended(tmp_path):
    args = arguments(tmp_path, "codex")
    original = b'mcp_servers = {other = {command = "keep"}}\n'
    args.config_file.write_bytes(original)
    with pytest.raises(MusicError, match="Cannot parse"):
        install_config(args)
    assert args.config_file.read_bytes() == original


def test_concurrent_change_is_detected_before_replacement(tmp_path):
    target = tmp_path / "settings"
    target.write_bytes(b"changed by client")
    with pytest.raises(MusicError, match="changed during setup"):
        write_config(target, b"old", b"new")
    assert target.read_bytes() == b"changed by client"
    assert list(tmp_path.iterdir()) == [target]


def test_failed_atomic_replacement_keeps_original_and_cleans_temporary(tmp_path, monkeypatch):
    target = tmp_path / "settings"
    target.write_bytes(b"original")

    def fail(*args):
        raise OSError("simulated filesystem error")

    monkeypatch.setattr("apple_music_mcp.install.os.replace", fail)
    with pytest.raises(OSError):
        write_config(target, b"original", b"updated")
    assert target.read_bytes() == b"original"
    assert not list(tmp_path.glob("*.tmp-*"))
    assert next(tmp_path.glob("*.backup-*")).read_bytes() == b"original"


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_backup_and_settings_are_private(tmp_path):
    args = arguments(tmp_path)
    args.config_file.write_text('{"secret": "must stay private"}')
    result = install_config(args)
    assert args.config_file.stat().st_mode & 0o777 == 0o600
    assert Path(result["backup"]).stat().st_mode & 0o777 == 0o600


def test_symlink_settings_require_explicit_real_path(tmp_path):
    target = tmp_path / "real"
    target.write_text("{}")
    args = arguments(tmp_path)
    try:
        args.config_file.symlink_to(target)
    except OSError:
        if sys.platform == "win32":
            pytest.skip("Windows symlinks require Developer Mode or administrator privileges")
        raise
    with pytest.raises(MusicError, match="symbolic link"):
        install_config(args)
    assert target.read_text() == "{}"


def test_project_scope_and_explicit_path_do_not_touch_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    args = build_parser().parse_args(
        ["install", "claude-code", "--scope", "project", "--project-dir", str(tmp_path / "project")]
    )
    result = install_config(args)
    assert Path(result["config_file"]) == tmp_path / "project/.mcp.json"
    assert not (tmp_path / "home").exists()
    with pytest.raises(MusicError, match="no project configuration"):
        project_config("claude-desktop", tmp_path)


def test_platform_paths_and_codex_home_override(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert user_config("claude-desktop") == (
        tmp_path / "Library/Application Support/Claude/claude_desktop_config.json"
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert user_config("vscode") == tmp_path / "roaming/Code/User/mcp.json"
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "custom-codex"))
    assert user_config("codex") == tmp_path / "custom-codex/config.toml"
    with pytest.raises(MusicError, match="--config-file"):
        user_config("generic")
