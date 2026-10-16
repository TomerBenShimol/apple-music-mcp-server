"""Small, typed MCP tool surface dedicated to music management."""

from __future__ import annotations

import asyncio
import functools
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from .api import MusicAPI
from .auth import MusicError
from .locking import MusicEditLock
from .native import NATIVE_ID, NativeMusic
from .signin import SignInManager

PageSize = Annotated[int, Field(ge=1, le=100)]
SearchSize = Annotated[int, Field(ge=1, le=25)]
MAX_OFFSET = 200_000
Offset = Annotated[int, Field(ge=0, le=MAX_OFFSET)]
SongIDs = Annotated[list[str], Field(min_length=1, max_length=100)]
Name = Annotated[str, Field(min_length=1, max_length=256)]
Query = Annotated[str, Field(min_length=1, max_length=200)]
Backend = Literal["auto", "web", "native"]

READ = {"readOnlyHint": True, "destructiveHint": False}
WRITE = {"readOnlyHint": False, "destructiveHint": False}
DELETE = {"readOnlyHint": False, "destructiveHint": True}


def user_errors(function):
    @functools.wraps(function)
    def invoke(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MusicError as exc:
            raise ToolError(str(exc)) from exc

    return invoke


def nonblank(value: str, label: str) -> str:
    if not value.strip():
        raise MusicError(f"{label} cannot be blank.")
    return value.strip()


class MusicService:
    def __init__(
        self,
        api: MusicAPI | None = None,
        native: NativeMusic | None = None,
        signin: SignInManager | None = None,
    ):
        self.api = api or MusicAPI()
        self.native = native or NativeMusic()
        self.lock = MusicEditLock(self.api.credentials.root)
        self.signin = signin or SignInManager(self.api.credentials)

    def use_web(self, backend: Backend) -> bool:
        return backend == "web" or (backend == "auto" and bool(self.api.credentials.user_token()))

    def native_ids(self, values: list[str]) -> list[str]:
        if not 1 <= len(values) <= 100 or len(set(v.upper() for v in values)) != len(values):
            raise MusicError("Supply 1–100 distinct native track IDs.")
        return [self.native.validate_id(v) for v in values]

    def all_native_tracks(self, playlist_id: str) -> list[dict]:
        tracks, offset = [], 0
        while True:
            result = self.native.call("playlist_tracks", id=playlist_id, limit=100, offset=offset)
            tracks.extend(result["items"])
            if result["next_offset"] is None:
                return tracks
            offset = result["next_offset"]
            if len(tracks) >= 20000:
                raise MusicError("Playlist exceeds the 20,000-track operation limit.")


def create_server(service: MusicService | None = None) -> FastMCP:
    service = service or MusicService()

    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield
        finally:
            await asyncio.to_thread(service.signin.close)

    mcp = FastMCP(
        "Apple Music",
        instructions=(
            "Manage the user's Apple Music library and playlists. Search before writing and "
            "use exact IDs returned by these tools. Numeric IDs identify catalog songs; "
            "i.… IDs identify web library songs; p.… IDs identify web playlists; 16-digit "
            "hexadecimal IDs identify local Music.app items. Never mix native and web IDs "
            "in one operation. Playlist removals take IDs from get_playlist_tracks. "
            "Removing from the library may also affect playlists and synced devices. "
            "Dry-run options preview edits. If a write outcome is uncertain, read the "
            "affected resource before retrying. Web responses marked accepted mean Apple "
            "accepted the request; Music sync may still be pending. Choose the appropriate "
            "tools for ordinary music requests; the user need not name MCP or a tool. "
            "When account sign-in is needed, use connect_apple_music, let the user complete "
            "Apple's local browser sign-in, then use get_status to verify web_accessible "
            "before retrying the requested edit. Do not use terminal commands for sign-in. "
            "Music.app read access does not imply web account write access. Never ask for "
            "an Apple password or verification code in chat."
        ),
        lifespan=lifespan,
    )

    @mcp.tool(annotations=READ)
    @user_errors
    def get_status(check_native: bool = False) -> dict:
        """Check web sign-in and optionally Music.app automation access. Never returns tokens."""
        signed_in = bool(service.api.credentials.user_token())
        result = {
            "web_signed_in": signed_in,
            "token_from_environment": service.api.credentials.user_token_from_environment(),
            "web_accessible": False,
            "credential_directory": str(service.api.credentials.root),
            "login_tool": "connect_apple_music",
            "sign_in": service.signin.status(),
        }
        result.update(service.api.check_access() if signed_in else {})
        result.update({"native": service.native.check_access()} if check_native else {})
        return result

    @mcp.tool(annotations=WRITE)
    @user_errors
    def connect_apple_music(
        timeout: Annotated[int, Field(ge=30, le=1800)] = 900,
    ) -> dict:
        """Start Apple Music account sign-in in a local browser, returning immediately.

        Use when the user requests or approves account connection. The user completes
        Apple's sign-in on this Mac; no password or verification code enters chat.
        get_status reports progress and verifies web_accessible before any music edit.
        Repeated calls while sign-in is active reuse the existing flow. Opens no shell.
        """
        return service.signin.start(timeout)

    @mcp.tool(annotations=READ)
    @user_errors
    def search_music(
        query: Query,
        kind: Literal["songs", "albums", "artists", "playlists"] = "songs",
        limit: SearchSize = 10,
        offset: Offset = 0,
    ) -> dict:
        """Search Apple's catalog without sign-in. Returns catalog IDs for library additions."""
        return service.api.search_catalog(nonblank(query, "Query"), kind, limit, offset)

    @mcp.tool(annotations=READ)
    @user_errors
    def search_library(
        query: str = "", limit: PageSize = 50, offset: Offset = 0, backend: Backend = "auto"
    ) -> dict:
        """Search your library; empty query browses songs. Web searches return at most 25 per page.

        backend='native' returns Music.app persistent IDs; auto uses web when signed in.
        """
        if len(query) > 200:
            raise MusicError("Query must be at most 200 characters.")
        if service.use_web(backend):
            return service.api.search_library(query.strip(), limit, offset)
        return service.native.call("search", query=query.strip(), limit=limit, offset=offset)

    @mcp.tool(annotations=READ)
    @user_errors
    def get_song_details(song_id: str) -> dict:
        """Get one exact song, using a catalog, web library, or native persistent ID."""
        if NATIVE_ID.fullmatch(song_id):
            return service.native.call("track", id=song_id)
        return service.api.get_song(song_id)

    @mcp.tool(annotations=WRITE)
    @user_errors
    def add_songs_to_library(catalog_song_ids: SongIDs, dry_run: bool = False) -> dict:
        """Add 1–100 catalog songs to your library. Requires the one-time web/MusicKit sign-in."""
        with service.lock:
            return service.api.add_library(catalog_song_ids, dry_run)

    @mcp.tool(annotations=DELETE)
    @user_errors
    def remove_songs_from_library(library_song_ids: SongIDs, dry_run: bool = False) -> dict:
        """Remove exact library songs. May remove them from playlists and synced devices.

        Use i.… IDs from web search_library or native 16-digit persistent IDs.
        Catalog IDs are rejected.
        """
        with service.lock:
            if all(NATIVE_ID.fullmatch(i) for i in library_song_ids):
                return service.native.call(
                    "remove_library",
                    track_ids=service.native_ids(library_song_ids),
                    dry_run=dry_run,
                )
            return service.api.remove_library(library_song_ids, dry_run)

    @mcp.tool(annotations=READ)
    @user_errors
    def list_playlists(limit: PageSize = 50, offset: Offset = 0, backend: Backend = "auto") -> dict:
        """List library playlists with their exact IDs. Use next_offset to continue."""
        if service.use_web(backend):
            return service.api.list_playlists(limit, offset)
        return service.native.call("playlists", limit=limit, offset=offset)

    @mcp.tool(annotations=READ)
    @user_errors
    def get_playlist_tracks(playlist_id: str, limit: PageSize = 100, offset: Offset = 0) -> dict:
        """Read playlist contents. These song IDs identify membership for playlist removals."""
        if NATIVE_ID.fullmatch(playlist_id):
            return service.native.call(
                "playlist_tracks", id=playlist_id, limit=limit, offset=offset
            )
        return service.api.playlist_tracks(playlist_id, limit, offset)

    @mcp.tool(annotations=WRITE)
    @user_errors
    def create_playlist(name: Name, description: str = "", backend: Backend = "auto") -> dict:
        """Create a normal library playlist and return its new ID."""
        name = nonblank(name, "Playlist name")
        if len(description) > 5000:
            raise MusicError("Description must be at most 5,000 characters.")
        with service.lock:
            if service.use_web(backend):
                return service.api.create_playlist(name, description)
            return service.native.call("create", name=name, description=description)

    @mcp.tool(annotations=WRITE)
    @user_errors
    def update_playlist(
        playlist_id: str,
        name: Name | None = None,
        description: str | None = None,
        dry_run: bool = False,
    ) -> dict:
        """Rename a playlist and/or update its description. Protected playlists are rejected."""
        changes = {}
        if name is not None:
            changes["name"] = nonblank(name, "Playlist name")
        if description is not None:
            if len(description) > 5000:
                raise MusicError("Description must be at most 5,000 characters.")
            changes["description"] = description
        if not changes:
            raise MusicError("Supply a name and/or description.")
        with service.lock:
            if NATIVE_ID.fullmatch(playlist_id):
                if dry_run:
                    return {
                        "dry_run": True,
                        "before": service.native.call("playlist", id=playlist_id),
                        "changes": changes,
                    }
                return service.native.call("update", id=playlist_id, **changes)
            return service.api.update_playlist(playlist_id, changes, dry_run)

    @mcp.tool(annotations=DELETE)
    @user_errors
    def delete_playlist(playlist_id: str, dry_run: bool = False) -> dict:
        """Delete one exact editable playlist. Songs stay in the library."""
        with service.lock:
            if NATIVE_ID.fullmatch(playlist_id):
                return service.native.call("delete_playlist", id=playlist_id, dry_run=dry_run)
            return service.api.delete_playlist(playlist_id, dry_run)

    @mcp.tool(annotations=WRITE)
    @user_errors
    def add_songs_to_playlist(
        playlist_id: str, song_ids: SongIDs, skip_duplicates: bool = True, dry_run: bool = False
    ) -> dict:
        """Append songs to a playlist, skipping existing songs by default.

        Web playlists accept numeric catalog IDs or i.… library IDs. Native playlists require native
        library IDs. Adding catalog songs to a web playlist does not explicitly add them to library;
        your Apple Music playlist settings determine that behavior.
        """
        with service.lock:
            if NATIVE_ID.fullmatch(playlist_id):
                return service.native.call(
                    "add",
                    id=playlist_id,
                    track_ids=service.native_ids(song_ids),
                    skip_duplicates=skip_duplicates,
                    dry_run=dry_run,
                )
            return service.api.add_playlist_tracks(playlist_id, song_ids, skip_duplicates, dry_run)

    @mcp.tool(annotations=DELETE)
    @user_errors
    def remove_songs_from_playlist(
        playlist_id: str, song_ids: SongIDs, dry_run: bool = False
    ) -> dict:
        """Remove songs only from this playlist, using IDs from get_playlist_tracks.

        Removes all occurrences of the supplied membership IDs; keeps the songs in your library.
        """
        with service.lock:
            if NATIVE_ID.fullmatch(playlist_id):
                return service.native.call(
                    "remove",
                    id=playlist_id,
                    track_ids=service.native_ids(song_ids),
                    dry_run=dry_run,
                )
            return service.api.remove_playlist_tracks(playlist_id, song_ids, dry_run)

    @mcp.tool(annotations=WRITE)
    @user_errors
    def duplicate_playlist(playlist_id: str, new_name: Name) -> dict:
        """Copy a playlist's ordered contents into a new playlist. Leaves the original intact."""
        new_name = nonblank(new_name, "Playlist name")
        with service.lock:
            if not NATIVE_ID.fullmatch(playlist_id):
                return service.api.copy_playlist(playlist_id, new_name)
            tracks = service.all_native_tracks(playlist_id)
            before = service.native.call("playlist", id=playlist_id)
            created = service.native.call(
                "create", name=new_name, description=before["description"]
            )
            copied = 0
            try:
                # Native add allows intentional duplicates for preserving the source contents.
                for offset in range(0, len(tracks), 100):
                    service.native.call(
                        "add",
                        id=created["id"],
                        track_ids=[i["id"] for i in tracks[offset : offset + 100]],
                        skip_duplicates=False,
                    )
                    copied += len(tracks[offset : offset + 100])
            except MusicError as exc:
                raise MusicError(
                    f"Created playlist {created['id']}; copied {copied} songs. {exc}"
                ) from exc
            return {"playlist": created, "copied_tracks": copied}

    @mcp.tool(annotations=DELETE)
    @user_errors
    def reorder_playlist(
        playlist_id: str,
        ordered_song_ids: Annotated[list[str], Field(max_length=20000)],
        dry_run: bool = False,
    ) -> dict:
        """Reorder a native Music.app playlist, keeping its ID and all song occurrences.

        Use list_playlists(backend='native') and native IDs. Supply every current song in
        the desired order, including duplicates. A recovery copy is kept during the edit.
        Web playlists cannot be reordered by this tool.
        """
        if not NATIVE_ID.fullmatch(playlist_id):
            raise MusicError(
                "Reordering requires a native Music.app playlist ID. "
                "Call list_playlists(backend='native') and get_playlist_tracks."
            )
        ids = [service.native.validate_id(i) for i in ordered_song_ids]
        with service.lock:
            return service.native.call("reorder", id=playlist_id, track_ids=ids, dry_run=dry_run)

    @mcp.tool(annotations=WRITE)
    @user_errors
    def import_audio_files(
        paths: Annotated[list[str], Field(min_length=1, max_length=25)], dry_run: bool = False
    ) -> dict:
        """Import local audio into Music.app. Use add_songs_to_library for catalog songs."""
        resolved = []
        for value in paths:
            path = Path(value).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() not in {
                ".mp3",
                ".m4a",
                ".aac",
                ".wav",
                ".aif",
                ".aiff",
                ".alac",
                ".mp4",
            }:
                raise MusicError("Each path must identify an existing supported audio file.")
            resolved.append(str(path))
        if dry_run:
            return {"dry_run": True, "importing": resolved}
        with service.lock:
            return service.native.call("import", paths=resolved)

    return mcp
