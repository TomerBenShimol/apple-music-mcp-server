import threading

import pytest

from apple_music_mcp.auth import Credentials, MusicError
from apple_music_mcp.signin import SignInManager


def test_signin_returns_before_human_finishes_and_deduplicates_clients(tmp_path, monkeypatch):
    credentials = Credentials(tmp_path)
    ready, finish = threading.Event(), threading.Event()
    calls = []

    def login(candidate, *, timeout, on_ready, cancelled):
        calls.append(candidate)
        assert timeout == 900
        on_ready()
        ready.set()
        assert finish.wait(5)
        candidate.save_user_token("verified" * 10, source="web")
        return "il"

    monkeypatch.setattr("apple_music_mcp.signin.browser_login", login)
    manager, other_client = SignInManager(credentials), SignInManager(credentials)
    try:
        assert manager.start()["status"] in {"starting", "waiting_for_sign_in"}
        assert ready.wait(5)
        assert manager.start()["already_running"]
        assert other_client.start()["status"] == "already_running"
        assert other_client.status()["status"] == "waiting_for_sign_in"
        assert credentials.user_token() is None
        assert len(calls) == 1
    finally:
        finish.set()
        manager.close()
    assert manager.status() == {"status": "connected", "storefront": "il"}
    assert credentials.user_token() == "verified" * 10
    assert "verified" not in manager.state_path.read_text()
    assert manager.state_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "error", [MusicError("Apple rejected access"), RuntimeError("private-url")]
)
def test_signin_failure_is_visible_without_exposing_private_browser_errors(
    tmp_path, monkeypatch, error
):
    def login(*args, **kwargs):
        raise error

    monkeypatch.setattr("apple_music_mcp.signin.browser_login", login)
    manager = SignInManager(Credentials(tmp_path))
    manager.start()
    manager.close()
    state = manager.status()
    assert state["status"] in {"failed", "cancelled"}
    assert "private-url" not in state["message"]
    assert manager.credentials.user_token() is None
    # A failed attempt releases the shared lock, so another client can reconnect.
    other = SignInManager(manager.credentials)
    assert other.start()["status"] != "already_running"
    other.close()


def test_mcp_shutdown_cancels_signin_and_waits_for_browser_cleanup(tmp_path, monkeypatch):
    ready, cleaned = threading.Event(), threading.Event()

    def login(*args, on_ready, cancelled, **kwargs):
        on_ready()
        ready.set()
        try:
            assert cancelled.wait(5)
            raise MusicError("Apple Music sign-in was cancelled.")
        finally:
            cleaned.set()

    monkeypatch.setattr("apple_music_mcp.signin.browser_login", login)
    manager = SignInManager(Credentials(tmp_path))
    manager.start()
    assert ready.wait(5)
    manager.close()
    assert cleaned.is_set()
    assert not manager.thread.is_alive()
    assert manager.status()["status"] == "cancelled"


def test_signin_refuses_while_an_environment_token_overrides_it(tmp_path, monkeypatch):
    monkeypatch.setenv("APPLE_MUSIC_USER_TOKEN", "e" * 40)
    monkeypatch.setattr(
        "apple_music_mcp.signin.browser_login", lambda *a, **kw: pytest.fail("browser opened")
    )
    result = SignInManager(Credentials(tmp_path)).start()
    assert result["status"] == "blocked"
    assert "APPLE_MUSIC_USER_TOKEN" in result["message"]


def test_starting_a_signin_removes_profiles_left_by_an_interrupted_one(tmp_path, monkeypatch):
    stale = tmp_path / ".signin-abc123"
    stale.mkdir(parents=True)
    (stale / "Cookies").write_text("session")
    monkeypatch.setattr("apple_music_mcp.signin.browser_login", lambda *a, **kw: "il")
    manager = SignInManager(Credentials(tmp_path))
    manager.start()
    manager.close()
    assert not stale.exists()
