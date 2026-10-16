import importlib.util
import json
import plistlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def service(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "scripts/chatgpt_service.py"
    spec = importlib.util.spec_from_file_location("chatgpt_service", source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    for name, value in {
        "ROOT": tmp_path / "runtime",
        "HERE": tmp_path / "runtime/chatgpt",
        "CLIENT": tmp_path / "runtime/chatgpt/tunnel-client",
        "PYTHON": tmp_path / "runtime/.venv/bin/python",
        "PROFILE_FILE": tmp_path / "profile.json",
        "FOREGROUND_PROFILE_FILE": tmp_path / "foreground.json",
        "PLIST": tmp_path / "LaunchAgents/service.plist",
        "LOGS": tmp_path / "logs",
    }.items():
        monkeypatch.setattr(module, name, value)
    module.CLIENT.parent.mkdir(parents=True)
    module.CLIENT.touch()
    module.PYTHON.parent.mkdir(parents=True)
    module.PYTHON.touch()
    module.PROFILE_FILE.write_text(json.dumps({"control_plane": {"tunnel_id": "tunnel_test"}}))
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(module.getpass, "getpass", lambda *_: "test-key-never-in-a-file")
    stored = {}

    class FakeKeychain:
        def save(self, account, value):
            stored[account] = value

        def read(self, account):
            return stored[account]

        def read_optional(self, account):
            return stored.get(account)

        def delete(self, account):
            stored.pop(account, None)

    monkeypatch.setattr(module, "Keychain", FakeKeychain)
    module.test_keychain = stored
    monkeypatch.setattr(
        module.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0)
    )
    monkeypatch.setattr(module.socket, "socket", lambda: SimpleSocket())
    return module


class SimpleSocket:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def setsockopt(self, *args):
        pass

    def bind(self, address):
        pass


def test_startup_failure_keeps_foreground_and_no_secret_file(service, monkeypatch):
    monkeypatch.setattr(service, "ready", lambda: False)
    clock = iter([0, 61])
    monkeypatch.setattr(service.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(service, "launchctl", lambda *a, **kw: None)
    monkeypatch.setattr(service, "stop_foreground", lambda: pytest.fail("old connection stopped"))
    with pytest.raises(RuntimeError, match="previous background connection was restored"):
        service.install()
    assert not service.PLIST.exists()
    assert "tunnel_test" not in service.test_keychain
    for file in service.ROOT.parent.rglob("*"):
        if file.is_file():
            assert b"test-key-never-in-a-file" not in file.read_bytes()


def test_ready_service_replaces_foreground_and_plist_has_no_key(service, monkeypatch):
    events = []
    monkeypatch.setattr(service, "launchctl", lambda *a, **kw: events.append(a[0]))
    monkeypatch.setattr(service, "ready", lambda: events.append("ready") or True)
    monkeypatch.setattr(service, "stop_foreground", lambda: events.append("stop-old"))
    assert service.install() == 0
    assert events == ["bootout", "bootstrap", "ready", "stop-old"]
    manifest = plistlib.loads(service.PLIST.read_bytes())
    assert "EnvironmentVariables" not in manifest
    assert b"test-key-never-in-a-file" not in service.PLIST.read_bytes()
    assert service.PLIST.stat().st_mode & 0o777 == 0o600


def test_run_passes_key_only_in_environment(service, monkeypatch):
    monkeypatch.setattr(service, "Keychain", lambda: SimpleNamespace(read=lambda _: "test-key"))
    monkeypatch.setenv("LOG_HTTP_RAW_UNSAFE", "true")
    monkeypatch.setenv("CONTROL_PLANE_BASE_URL", "https://unrelated.example")
    observed = []
    monkeypatch.setattr(service.os, "chdir", lambda *_: None)
    monkeypatch.setattr(service.os, "umask", lambda *_: None)
    monkeypatch.setattr(service.os, "execve", lambda *args: observed.append(args))
    service.run()
    _, args, env = observed[0]
    assert "test-key" not in args
    assert env["CONTROL_PLANE_API_KEY"] == "test-key"
    assert "LOG_HTTP_RAW_UNSAFE" not in env
    assert "CONTROL_PLANE_BASE_URL" not in env
    assert "--health.listen-addr" in args


def test_foreground_replacement_targets_only_exact_existing_tunnel(service, monkeypatch):
    client = str(Path.home() / "Desktop/apple-music-mcp/.chatgpt/tunnel-client")
    listing = (
        f"123 {client} run --profile apple-music-chatgpt "
        f"--profile-dir {service.CONFIG_DIR} --flag\n"
        f"124 {client} run --profile unrelated --profile-dir {service.CONFIG_DIR}\n"
        f"125 /other/tunnel-client run --profile apple-music-chatgpt\n"
    )
    monkeypatch.setattr(service.subprocess, "check_output", lambda *a, **kw: listing)
    killed = []
    monkeypatch.setattr(service.os, "kill", lambda pid, sig: killed.append(pid))
    service.stop_foreground()
    assert killed == [123]


def test_failed_reinstall_restores_the_working_key_and_service(service, monkeypatch):
    service.test_keychain["tunnel_test"] = "old-working-key"
    service.PLIST.parent.mkdir(parents=True)
    service.PLIST.write_bytes(b"old plist")
    events = []
    monkeypatch.setattr(service, "launchctl", lambda *a, **kw: events.append(a[0]))
    monkeypatch.setattr(service, "ready", lambda: False)
    clock = iter([0, 61])
    monkeypatch.setattr(service.time, "monotonic", lambda: next(clock))
    with pytest.raises(RuntimeError, match="previous background connection was restored"):
        service.install()
    assert service.test_keychain["tunnel_test"] == "old-working-key"
    assert service.PLIST.read_bytes() == b"old plist"
    assert events[-1] == "bootstrap"


def test_install_derives_the_background_profile_from_the_foreground_one(service, monkeypatch):
    profile = service.PROFILE_FILE.read_text()
    service.PROFILE_FILE.unlink()
    service.FOREGROUND_PROFILE_FILE.write_text(profile)
    monkeypatch.setattr(service, "launchctl", lambda *a, **kw: None)
    monkeypatch.setattr(service, "ready", lambda: True)
    monkeypatch.setattr(service, "stop_foreground", lambda: None)
    assert service.install() == 0
    assert service.PROFILE_FILE.read_text() == profile
    assert service.PROFILE_FILE.stat().st_mode & 0o777 == 0o600


def test_install_without_any_profile_explains_the_first_step(service):
    service.PROFILE_FILE.unlink()
    with pytest.raises(RuntimeError, match=r"scripts/connect_chatgpt\.py"):
        service.install()


def test_tunnel_ids_with_dashes_are_accepted(service):
    service.PROFILE_FILE.write_text('{"control_plane": {"tunnel_id": "tunnel_a-b"}}')
    assert service.read_settings()[1] == "tunnel_a-b"
