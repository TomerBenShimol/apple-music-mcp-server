import base64
import json
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import httpx
import pytest

from apple_music_mcp.auth import Credentials, MusicError, login_server, verify_user_token
from apple_music_mcp.browser_login import browser_login, music_token
from apple_music_mcp.native import NativeMusic


def test_saved_credentials_are_private_and_can_be_replaced(tmp_path):
    credentials = Credentials(tmp_path / "private")
    credentials.save_user_token("a" * 40)
    path = credentials.root / "credentials.json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    credentials.save_user_token("b" * 40)
    assert credentials.user_token() == "b" * 40
    assert not list(credentials.root.glob(".music-*"))


def test_login_callback_checks_origin_and_capability(tmp_path, monkeypatch):
    monkeypatch.setattr("apple_music_mcp.auth.verify_user_token", lambda *a, **kw: "il")
    credentials = Credentials(tmp_path)
    server, url = login_server(credentials, "public-test-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client() as client:
            assert client.get(url).status_code == 200
            assert client.get(url, headers={"Host": "evil.example"}).status_code == 404
            token = {"token": "a" * 40}
            assert (
                client.post(
                    url + "/token", json=token, headers={"Origin": "https://evil.example"}
                ).status_code
                == 403
            )
            assert credentials.user_token() is None
            origin = "http://" + urlsplit(url).netloc
            assert (
                client.post(url + "/token", json=token, headers={"Origin": origin}).status_code
                == 200
            )
            assert server.authorized and credentials.user_token() == "a" * 40
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_web_player_token_cannot_use_local_musickit(tmp_path):
    payload = base64.urlsafe_b64encode(b'{"iss":"AMPWebPlay"}').decode().rstrip("=")
    with pytest.raises(MusicError, match="login --web"):
        login_server(Credentials(tmp_path), "header." + payload + ".signature")


def test_web_cookie_selector_ignores_other_account_credentials():
    cookies = [
        {"name": "account-token", "domain": ".apple.com", "secure": True, "value": "a" * 40},
        {"name": "media-user-token", "domain": "evil.apple.com", "secure": True, "value": "b" * 40},
        {"name": "media-user-token", "domain": ".apple.com", "secure": False, "value": "c" * 40},
    ]
    assert music_token(cookies) is None
    cookies.append(
        {
            "name": "media-user-token",
            "domain": ".music.apple.com",
            "secure": True,
            "value": "d" * 40,
        }
    )
    assert music_token(cookies) == "d" * 40


def test_candidate_verification_uses_web_api_and_keeps_old_token(tmp_path, monkeypatch):
    credentials = Credentials(tmp_path)
    credentials.save_user_token("old" * 20)
    calls = []

    def developer(client, force_web=False):
        assert force_web
        return "public-token", True

    monkeypatch.setattr(credentials, "developer_token", developer)

    def handler(request):
        calls.append(request)
        assert request.url.host == "amp-api.music.apple.com"
        assert request.headers["Music-User-Token"] == "candidate" * 10
        if request.url.path.endswith("storefront"):
            return httpx.Response(200, json={"data": [{"id": "il"}]})
        return httpx.Response(403)

    real_client = httpx.Client
    monkeypatch.setattr(
        "apple_music_mcp.auth.httpx.Client",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    with pytest.raises(MusicError, match="rejected access"):
        verify_user_token(credentials, "candidate" * 10, web=True)
    assert len(calls) == 2
    assert credentials.user_token() == "old" * 20


def test_web_token_source_is_saved_and_selects_web_api(tmp_path, monkeypatch):
    from apple_music_mcp.api import MusicAPI

    credentials = Credentials(tmp_path)
    credentials.save_user_token("user" * 20, source="web")
    assert credentials.user_token_source() == "web"

    def developer(client, force_web=False):
        assert force_web
        return "public-token", True

    monkeypatch.setattr(credentials, "developer_token", developer)
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    ) as client:
        MusicAPI(credentials, client).request("GET", "/v1/me/library/songs")


@pytest.mark.parametrize("rejected", [False, True])
def test_browser_login_cleans_profile_and_saves_only_verified_music_token(
    tmp_path, monkeypatch, rejected, capsys
):
    credentials = Credentials(tmp_path / "private")
    credentials.save_user_token("old" * 20)
    observed = {}

    class Context:
        def __init__(self):
            self.pages = [SimpleNamespace(goto=self.goto)]

        def goto(self, url, **kwargs):
            assert url == "https://music.apple.com/"

        def cookies(self, url):
            assert observed["ready"]
            assert url == "https://music.apple.com"
            return [
                {
                    "name": "media-user-token",
                    "domain": ".apple.com",
                    "secure": True,
                    "value": "new" * 20,
                }
            ]

        def close(self):
            observed["closed"] = True

    def launch(profile, **kwargs):
        observed["profile"] = Path(profile)
        assert Path(profile).stat().st_mode & 0o777 == 0o700
        assert kwargs["chromium_sandbox"] is True
        assert kwargs["headless"] is False
        return Context()

    class Playwright:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch))

        def __exit__(self, *args):
            pass

    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "playwright.sync_api",
        SimpleNamespace(Error=RuntimeError, sync_playwright=Playwright),
    )

    def verify(candidate_credentials, token, *, web):
        assert candidate_credentials is credentials and token == "new" * 20 and web
        if rejected:
            raise MusicError("Apple rejected the candidate")
        return "il"

    monkeypatch.setattr("apple_music_mcp.browser_login.verify_user_token", verify)

    def ready():
        observed["ready"] = True

    if rejected:
        with pytest.raises(MusicError, match="rejected the candidate"):
            browser_login(credentials, on_ready=ready)
        assert credentials.user_token() == "old" * 20
    else:
        assert browser_login(credentials, on_ready=ready) == "il"
        assert credentials.user_token() == "new" * 20
        assert credentials.user_token_source() == "web"
    assert observed["closed"]
    assert not observed["profile"].exists()
    assert list(credentials.root.iterdir()) == [credentials.root / "credentials.json"]
    output = capsys.readouterr()
    assert output.out == ""  # MCP stdout stays reserved for JSON-RPC.
    assert "Waiting for music access" in output.err


def test_invalid_token_does_not_replace_existing_credentials(tmp_path):
    credentials = Credentials(tmp_path)
    credentials.save_user_token("a" * 40)
    with pytest.raises(MusicError):
        credentials.save_user_token("bad token")
    assert credentials.user_token() == "a" * 40


def test_native_input_is_data_not_interpolated_script(monkeypatch):
    captured = []

    def run(command, **kwargs):
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, '{"items":[]}', "")

    monkeypatch.setattr("apple_music_mcp.native.sys.platform", "darwin")
    monkeypatch.setattr("apple_music_mcp.native.subprocess.run", run)
    query = '"; doShellScript("touch /tmp/should-never-run"); //'
    NativeMusic().call("search", query=query)
    command = captured[0]
    assert command[3].endswith("music.js")
    assert json.loads(command[-1])["query"] == query


def test_native_rejects_untrusted_ids_before_running(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("osascript should not run")

    monkeypatch.setattr("apple_music_mcp.native.sys.platform", "darwin")
    monkeypatch.setattr("apple_music_mcp.native.subprocess.run", forbidden)
    with pytest.raises(MusicError, match="16-digit"):
        NativeMusic().call("delete_playlist", id='bad";delete library')


def test_native_write_timeout_warns_about_uncertain_outcome(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 25)

    monkeypatch.setattr("apple_music_mcp.native.sys.platform", "darwin")
    monkeypatch.setattr("apple_music_mcp.native.subprocess.run", timeout)
    with pytest.raises(MusicError, match="outcome is uncertain"):
        NativeMusic().call("remove_library", track_ids=["0123456789ABCDEF"])
