import json
import sys
import tomllib
from pathlib import Path

import pytest

from apple_music_mcp.auth import MusicError
from apple_music_mcp.cli import build_parser
from apple_music_mcp.clients import CLIENTS, render_config, server_entry, show_config


@pytest.mark.parametrize("client", CLIENTS)
def test_config_round_trip_uses_same_server_and_credentials(client, tmp_path, monkeypatch):
    monkeypatch.setenv("APPLE_MUSIC_USER_TOKEN", "secret-must-not-be-exported")
    entry = server_entry(client, Path(sys.executable), tmp_path / "music settings", "GB")
    rendered = render_config(client, "apple-music", entry)
    parser = tomllib.loads if client == "codex" else json.loads
    decoded = parser(rendered)[CLIENTS[client].root_key]["apple-music"]
    assert decoded["args"] == ["-m", "apple_music_mcp", "serve"]
    assert decoded["env"] == {
        "APPLE_MUSIC_MCP_HOME": str(tmp_path / "music settings"),
        "APPLE_MUSIC_STOREFRONT": "gb",
    }
    assert "secret-must-not-be-exported" not in rendered
    assert "trust" not in decoded and "autoApprove" not in decoded


def test_virtualenv_python_symlink_is_preserved(tmp_path):
    interpreter = tmp_path / "virtual environment/bin/python"
    interpreter.parent.mkdir(parents=True)
    try:
        interpreter.symlink_to(sys.executable)
    except OSError:
        if sys.platform == "win32":
            pytest.skip("Windows symlinks require Developer Mode or administrator privileges")
        raise
    entry = server_entry("cursor", interpreter, tmp_path, None)
    assert entry["command"] == str(interpreter)
    assert "APPLE_MUSIC_STOREFRONT" not in entry["env"]


def test_codex_config_preserves_unicode_paths_without_invalid_surrogate_escapes(tmp_path):
    interpreter = tmp_path / "music 🎵/python"
    interpreter.parent.mkdir()
    interpreter.touch()
    entry = server_entry("codex", interpreter, tmp_path / "library 🎵", None)
    decoded = tomllib.loads(render_config("codex", "apple-music", entry))
    assert decoded["mcp_servers"]["apple-music"] == entry


@pytest.mark.parametrize("name", ["has_underscore", "bad.name", "../name", "a" * 49])
def test_invalid_server_name_cannot_create_nested_tables(name):
    with pytest.raises(MusicError, match="server name"):
        render_config("codex", name, {})


def test_missing_interpreter_and_invalid_storefront_are_actionable(tmp_path):
    with pytest.raises(MusicError, match="Python executable"):
        server_entry("cursor", tmp_path / "missing", tmp_path, None)
    with pytest.raises(MusicError, match="two-letter"):
        server_entry("cursor", Path(sys.executable), tmp_path, "invalid")


def test_cli_config_does_not_create_directories(tmp_path, capsys):
    target = tmp_path / "not-created"
    args = build_parser().parse_args(["config", "vscode", "--data-dir", str(target)])
    show_config(args)
    config = json.loads(capsys.readouterr().out)
    assert config["servers"]["apple-music"]["type"] == "stdio"
    assert not target.exists()
