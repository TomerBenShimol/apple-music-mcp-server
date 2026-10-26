import itertools
import sys
from types import SimpleNamespace

import pytest

from apple_music_mcp.auth import Credentials, MusicError, TransientMusicError
from apple_music_mcp.browser_login import browser_login

COOKIE = {"name": "media-user-token", "domain": ".apple.com", "secure": True, "value": "n" * 40}


@pytest.fixture
def browser_launches():
    return []


@pytest.fixture
def fake_browser(monkeypatch, browser_launches):
    waits = []

    class Context:
        def __init__(self):
            self.pages = [
                SimpleNamespace(goto=lambda url, **kw: None, wait_for_timeout=waits.append)
            ]

        def cookies(self, url):
            return [COOKIE]

        def close(self):
            pass

    class Playwright:
        def __enter__(self):
            def launch(profile, **kwargs):
                browser_launches.append(kwargs)
                return Context()

            chromium = SimpleNamespace(launch_persistent_context=launch)
            return SimpleNamespace(chromium=chromium)

        def __exit__(self, *args):
            pass

    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "playwright.sync_api",
        SimpleNamespace(Error=RuntimeError, sync_playwright=Playwright),
    )
    return waits


def test_transient_verification_failure_is_retried(tmp_path, monkeypatch, fake_browser):
    outcomes = iter([TransientMusicError("Could not reach Apple Music."), "il"])

    def verify(credentials, token, *, web):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr("apple_music_mcp.browser_login.verify_user_token", verify)
    credentials = Credentials(tmp_path)
    assert browser_login(credentials) == "il"
    assert credentials.user_token() == "n" * 40
    assert 10000 in fake_browser


def test_persistent_transient_failure_ends_in_timeout(tmp_path, monkeypatch, fake_browser):
    def verify(credentials, token, *, web):
        raise TransientMusicError("Could not reach Apple Music.")

    ticks = itertools.count(0, 30)
    monkeypatch.setattr("apple_music_mcp.browser_login.verify_user_token", verify)
    monkeypatch.setattr("apple_music_mcp.browser_login.time.monotonic", lambda: next(ticks))
    with pytest.raises(MusicError, match="timed out"):
        browser_login(Credentials(tmp_path), timeout=60)


def test_rejection_is_not_retried(tmp_path, monkeypatch, fake_browser):
    calls = []

    def verify(credentials, token, *, web):
        calls.append(token)
        raise MusicError("Apple Music rejected access.")

    monkeypatch.setattr("apple_music_mcp.browser_login.verify_user_token", verify)
    with pytest.raises(MusicError, match="rejected access"):
        browser_login(Credentials(tmp_path))
    assert len(calls) == 1


def test_windows_signin_uses_bundled_chromium_and_cleans_profile(
    tmp_path, monkeypatch, fake_browser, browser_launches
):
    from apple_music_mcp import browser_login as module

    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="win32", stderr=sys.stderr))
    monkeypatch.setattr(module, "verify_user_token", lambda *args, **kwargs: "us")
    credentials = Credentials(tmp_path / "Music 音楽")
    assert browser_login(credentials) == "us"
    assert browser_launches == [{"channel": None, "headless": False, "chromium_sandbox": True}]
    assert credentials.user_token() == COOKIE["value"]
    assert not list(credentials.root.glob(".signin-*"))
