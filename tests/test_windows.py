"""Windows capability/routing tests also run on macOS without changing the host OS."""

import errno
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from apple_music_mcp import process_lock
from apple_music_mcp.auth import Credentials, MusicError, private_json, read_json
from apple_music_mcp.capabilities import NATIVE_TOOLS, capabilities
from apple_music_mcp.server import MusicService, create_server


@pytest.fixture
def windows_service(tmp_path, monkeypatch):
    monkeypatch.setattr("apple_music_mcp.capabilities.supports_native", lambda: False)
    api = MagicMock()
    api.credentials = Credentials(tmp_path / "music library 音楽")
    native = MagicMock()
    service = MusicService(api=api, native=native)
    native.reset_mock()  # Ignore constructor truthiness checks.
    return service


async def test_windows_discovery_and_status_exclude_music_app(windows_service):
    async with Client(create_server(windows_service)) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert len(names) == 15
        assert not names.intersection(NATIVE_TOOLS)
        result = await client.call_tool("get_status", {"check_native": True})
        assert result.data["native_backend_available"] is False
        assert result.data["unavailable_tools"] == list(NATIVE_TOOLS)
        assert result.data["native"]["accessible"] is False
        assert result.data["web_signed_in"] is False
    assert not windows_service.native.mock_calls


@pytest.mark.parametrize(
    ("tool", "arguments", "method"),
    [
        ("search_music", {"query": "Artist"}, "search_catalog"),
        ("search_library", {"query": "Artist"}, "search_library"),
        ("get_song_details", {"song_id": "123"}, "get_song"),
        ("add_songs_to_library", {"catalog_song_ids": ["123"]}, "add_library"),
        ("remove_songs_from_library", {"library_song_ids": ["i.song"]}, "remove_library"),
        ("list_playlists", {}, "list_playlists"),
        ("get_playlist_tracks", {"playlist_id": "p.mix"}, "playlist_tracks"),
        ("create_playlist", {"name": "Evening"}, "create_playlist"),
        ("update_playlist", {"playlist_id": "p.mix", "name": "New"}, "update_playlist"),
        ("delete_playlist", {"playlist_id": "p.mix"}, "delete_playlist"),
        (
            "add_songs_to_playlist",
            {"playlist_id": "p.mix", "song_ids": ["123"]},
            "add_playlist_tracks",
        ),
        (
            "remove_songs_from_playlist",
            {"playlist_id": "p.mix", "song_ids": ["i.song"]},
            "remove_playlist_tracks",
        ),
        ("duplicate_playlist", {"playlist_id": "p.mix", "new_name": "Copy"}, "copy_playlist"),
    ],
)
async def test_windows_music_tools_use_web_without_native_fallback(
    windows_service, tool, arguments, method
):
    getattr(windows_service.api, method).return_value = {"backend": "web"}
    async with Client(create_server(windows_service)) as client:
        result = await client.call_tool(tool, arguments)
        assert result.data == {"backend": "web"}
    getattr(windows_service.api, method).assert_called_once()
    assert not windows_service.native.mock_calls


async def test_windows_missing_signin_returns_web_signin_error(windows_service):
    windows_service.api.search_library.side_effect = MusicError("Call connect_apple_music first.")
    async with Client(create_server(windows_service)) as client:
        with pytest.raises(ToolError, match="connect_apple_music"):
            await client.call_tool("search_library", {})
        with pytest.raises(ToolError, match="requires macOS"):
            await client.call_tool("list_playlists", {"backend": "native"})
        with pytest.raises(ToolError, match="requires macOS"):
            await client.call_tool("get_song_details", {"song_id": "0123456789ABCDEF"})
    assert not windows_service.native.mock_calls


def test_platform_capabilities_match_actual_host():
    report = capabilities()
    assert report["native_backend_available"] == (sys.platform == "darwin")
    assert report["unavailable_tools"] == ([] if sys.platform == "darwin" else list(NATIVE_TOOLS))


def test_saved_unicode_settings_use_utf8_even_with_a_legacy_locale(tmp_path, monkeypatch):
    target = tmp_path / "音楽" / "settings.json"
    value = {"description": "מוזיקה 日本語 🎵"}
    private_json(target, value)
    original = Path.read_text

    def legacy_read(self, encoding=None, **kwargs):
        return original(self, encoding=encoding or "cp1252", **kwargs)

    monkeypatch.setattr(Path, "read_text", legacy_read)
    assert read_json(target) == value
    assert json.loads(target.read_bytes()) == value


def test_windows_byte_lock_uses_same_range_for_acquire_and_release(tmp_path, monkeypatch):
    calls = []
    fd = process_lock.open_lock(tmp_path / "lock")
    os.lseek(fd, 20, os.SEEK_SET)
    fake = SimpleNamespace(LK_NBLCK=1, LK_UNLCK=0)
    fake.locking = lambda descriptor, mode, size: calls.append(
        (descriptor, mode, size, os.lseek(descriptor, 0, os.SEEK_CUR))
    )
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    monkeypatch.setattr(process_lock, "WINDOWS", True)
    try:
        process_lock.try_lock(fd)
    finally:
        process_lock.release_lock(fd)
    assert calls == [(fd, 1, 1, 0), (fd, 0, 1, 0)]
    with pytest.raises(OSError):
        os.fstat(fd)


@pytest.mark.parametrize("code", [errno.EACCES, errno.EAGAIN, errno.EDEADLK, errno.EBADF])
def test_windows_lock_contention_is_normalized_without_hiding_other_errors(
    tmp_path, monkeypatch, code
):
    def failed_lock(*_args):
        raise OSError(code, "Windows lock failure")

    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(LK_NBLCK=1, locking=failed_lock))
    monkeypatch.setattr(process_lock, "WINDOWS", True)
    fd = process_lock.open_lock(tmp_path / "lock")
    try:
        with pytest.raises(OSError) as caught:
            process_lock.try_lock(fd)
        assert isinstance(caught.value, BlockingIOError) == (code != errno.EBADF)
    finally:
        os.close(fd)
