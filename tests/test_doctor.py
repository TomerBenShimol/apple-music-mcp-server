import json
from types import SimpleNamespace

import pytest

from apple_music_mcp.capabilities import supports_native
from apple_music_mcp.doctor import diagnostics, doctor, probe_server, run_probe


def test_offline_report_never_reads_saved_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("apple_music_mcp.doctor.dependency_version", lambda _: "installed")
    (tmp_path / "credentials.json").write_text("invalid JSON containing a secret")
    report = diagnostics(tmp_path)
    assert report["status"] == "ready"
    assert report["saved_credentials_present"] is True
    assert "secret" not in json.dumps(report)
    assert report["account_access"].startswith("not_checked")


def test_missing_required_dependency_is_reported(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("apple_music_mcp.doctor.dependency_version", lambda _: None)
    with pytest.raises(SystemExit) as error:
        doctor(SimpleNamespace(data_dir=tmp_path, probe=False))
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "needs_attention"


def test_probe_failure_does_not_expose_exception_contents(tmp_path, monkeypatch):
    async def failed_probe(_credentials):
        raise RuntimeError("secret token in underlying client error")

    monkeypatch.setattr("apple_music_mcp.doctor.probe_server", failed_probe)
    report = run_probe(tmp_path)
    assert report == {"status": "needs_attention", "error_type": "RuntimeError"}


async def test_fresh_stdio_server_discovers_tools_without_signing_in(tmp_path):
    report = await probe_server(tmp_path)
    assert report["status"] == "ready"
    assert report["tool_count"] == (17 if supports_native() else 15)
    assert "create_playlist" in report["tools"]
    assert "remove_songs_from_library" in report["tools"]
    assert not list(tmp_path.iterdir())
