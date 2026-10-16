import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("doctor_code", [0, 2])
def test_chatgpt_setup_reuses_mcp_and_never_saves_api_key(tmp_path, monkeypatch, doctor_code):
    source = Path(__file__).resolve().parents[1] / "scripts/connect_chatgpt.py"
    spec = importlib.util.spec_from_file_location("chatgpt_setup", source)
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    setup.CLIENT = tmp_path / "tunnel-client"
    setup.CLIENT.touch()
    setup.RUNTIME = tmp_path / "runtime"
    (setup.RUNTIME / ".venv/bin").mkdir(parents=True)
    (setup.RUNTIME / ".venv/bin/python").touch()
    setup.PROFILE_DIR = tmp_path / "profiles"
    monkeypatch.setattr(setup.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda *a: "tunnel_test123456")
    monkeypatch.setattr(setup.getpass, "getpass", lambda *a: "sk-test-never-save")
    monkeypatch.setenv("CONTROL_PLANE_BASE_URL", "https://unrelated.example")
    monkeypatch.setenv("LOG_HTTP_RAW_UNSAFE", "true")
    observed = []

    def run(command, **kwargs):
        observed.append((command, kwargs))
        assert kwargs["env"]["CONTROL_PLANE_API_KEY"] == "sk-test-never-save"
        assert "CONTROL_PLANE_BASE_URL" not in kwargs["env"]
        assert "LOG_HTTP_RAW_UNSAFE" not in kwargs["env"]
        assert kwargs["cwd"] == setup.RUNTIME
        assert "sk-test-never-save" not in command
        return subprocess.CompletedProcess(command, doctor_code if command[1] == "doctor" else 0)

    monkeypatch.setattr(setup.subprocess, "run", run)
    assert setup.main() == doctor_code
    assert [command[1] for command, _ in observed] == (
        ["doctor"] if doctor_code else ["doctor", "run"]
    )
    profile = setup.PROFILE_DIR / (setup.PROFILE + ".yaml")
    contents = profile.read_text()
    assert "sk-test-never-save" not in contents
    settings = json.loads(contents)
    assert settings["control_plane"]["base_url"] == "https://api.openai.com"
    assert settings["control_plane"]["api_key"] == "env:CONTROL_PLANE_API_KEY"
    assert settings["health"]["listen_addr"] == "127.0.0.1:0"
    assert settings["mcp"]["stdio_send_initialized_notification"] is True
    assert settings["mcp"]["commands"][0]["command"].endswith("-m apple_music_mcp serve")
    assert profile.stat().st_mode & 0o777 == 0o600
