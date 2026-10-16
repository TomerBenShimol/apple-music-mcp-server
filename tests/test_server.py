from unittest.mock import MagicMock

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from apple_music_mcp.auth import MusicError
from apple_music_mcp.server import MusicService, create_server


@pytest.fixture
def service(tmp_path):
    native = MagicMock()
    native.validate_id.side_effect = lambda value: value.upper()
    api = MagicMock()
    api.credentials.user_token.return_value = None
    api.credentials.root = tmp_path
    api.credentials.user_token_from_environment.return_value = False
    return MusicService(api=api, native=native)


async def test_tools_have_correct_mutation_annotations(service):
    async with Client(create_server(service)) as client:
        tools = {t.name: t for t in await client.list_tools()}
        assert len(tools) == 17
        assert tools["search_music"].annotations.readOnlyHint
        assert tools["delete_playlist"].annotations.destructiveHint
        assert not tools["add_songs_to_library"].annotations.readOnlyHint
        assert not tools["connect_apple_music"].annotations.readOnlyHint


async def test_account_connection_is_a_tool_and_status_points_to_it(service):
    service.signin = MagicMock()
    service.signin.start.return_value = {"status": "starting"}
    service.signin.status.return_value = {"status": "waiting_for_sign_in"}
    async with Client(create_server(service)) as client:
        result = await client.call_tool("connect_apple_music", {})
        assert result.data == {"status": "starting"}
        result = await client.call_tool("get_status", {})
        assert result.data["login_tool"] == "connect_apple_music"
        assert result.data["sign_in"]["status"] == "waiting_for_sign_in"
        assert "login_command" not in result.data
        with pytest.raises(ToolError):
            await client.call_tool("connect_apple_music", {"timeout": 999999})
    service.signin.start.assert_called_once_with(900)
    service.signin.close.assert_called_once()


async def test_schema_rejects_bad_limits_and_empty_mutation_before_backend(service):
    async with Client(create_server(service)) as client:
        with pytest.raises(ToolError):
            await client.call_tool("search_music", {"query": "Artist", "limit": 1000})
        with pytest.raises(ToolError):
            await client.call_tool("add_songs_to_library", {"catalog_song_ids": []})
    service.api.search_catalog.assert_not_called()
    service.api.add_library.assert_not_called()


async def test_native_and_web_ids_are_routed_to_the_correct_backend(service):
    service.native.call.return_value = {"items": []}
    service.api.playlist_tracks.return_value = {"items": []}
    async with Client(create_server(service)) as client:
        await client.call_tool("get_playlist_tracks", {"playlist_id": "0123456789ABCDEF"})
        await client.call_tool("get_playlist_tracks", {"playlist_id": "p.web"})
    service.native.call.assert_called_once_with(
        "playlist_tracks", id="0123456789ABCDEF", limit=100, offset=0
    )
    service.api.playlist_tracks.assert_called_once_with("p.web", 100, 0)


async def test_actionable_backend_errors_survive_mcp(service):
    service.api.search_catalog.side_effect = MusicError("Apple Music rate-limited this connection.")
    async with Client(create_server(service)) as client:
        with pytest.raises(ToolError, match="rate-limited"):
            await client.call_tool("search_music", {"query": "Artist"})


async def test_blank_names_do_not_create_playlists(service):
    async with Client(create_server(service)) as client:
        with pytest.raises(ToolError, match="cannot be blank"):
            await client.call_tool("create_playlist", {"name": "  "})
    service.native.call.assert_not_called()


async def test_auto_backend_prefers_authenticated_web_without_touching_music(service):
    service.api.credentials.user_token.return_value = "test-token"
    service.api.list_playlists.return_value = {"items": []}
    async with Client(create_server(service)) as client:
        await client.call_tool("list_playlists", {})
    service.api.list_playlists.assert_called_once_with(50, 0)
    service.native.call.assert_not_called()


async def test_status_says_when_the_environment_supplies_the_token(service):
    service.signin = MagicMock()
    service.signin.status.return_value = {"status": "not_started"}
    service.api.credentials.user_token_from_environment.return_value = True
    async with Client(create_server(service)) as client:
        result = await client.call_tool("get_status", {})
    assert result.data["token_from_environment"] is True


async def test_next_offset_past_20000_is_accepted(service):
    service.api.credentials.user_token.return_value = "t"
    service.api.search_library.return_value = {"items": []}
    async with Client(create_server(service)) as client:
        await client.call_tool("search_library", {"offset": 20100})
    service.api.search_library.assert_called_once_with("", 50, 20100)


async def test_reorder_names_a_recovery_playlist_for_the_native_call(service):
    service.native.call.return_value = {"changed": False}
    async with Client(create_server(service)) as client:
        await client.call_tool(
            "reorder_playlist",
            {"playlist_id": "0123456789ABCDEF", "ordered_song_ids": ["00000000000000AA"]},
        )
    kwargs = service.native.call.call_args.kwargs
    assert kwargs["backup_name"].startswith("MCP recovery 0123456789ABCDEF ")
