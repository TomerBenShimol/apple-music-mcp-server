"""Apple catalog and library requests.

The web-player backend is an undocumented compatibility route. Official
developer tokens use the documented public host; web-only edits use Apple's
public web-player token. Failures are surfaced, never disguised as empty search.
"""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qs, urlsplit

import httpx

from .auth import Credentials, MusicError, TransientMusicError

WEB_ORIGIN = "https://amp-api.music.apple.com"
PUBLIC_ORIGIN = "https://api.music.apple.com"
LIBRARY_SONG_ID = re.compile(r"i\.[A-Za-z0-9.\-]+\Z")
PLAYLIST_ID = re.compile(r"p\.[A-Za-z0-9.\-]+\Z")
CATALOG_ID = re.compile(r"[0-9]+\Z")


NOT_SIGNED_IN = (
    "Apple Music is not signed in. Use the connect_apple_music tool, let the user "
    "complete sign-in in the local browser, then check get_status before retrying."
)
REJECTED = (
    "Apple Music rejected access. Reconnect using the connect_apple_music tool; "
    "check that this account has an active Apple Music subscription."
)
NOT_FOUND = "Apple Music could not find this resource in this account/storefront."
UNCERTAIN_WRITE = " The write outcome is uncertain; inspect the library before retrying."


def validate_path(path: str) -> None:
    # Never follow pagination to another origin or send music tokens to arbitrary URLs.
    if not path.startswith("/v1/") or urlsplit(path).netloc or ".." in path:
        raise MusicError("Invalid Apple Music API path.")


def auth_headers(token: str, user_token: str | None) -> dict:
    personal = {"Music-User-Token": user_token} if user_token else {}
    return {"Authorization": "Bearer " + token, "Origin": "https://music.apple.com", **personal}


def rate_limited(response: httpx.Response) -> TransientMusicError:
    retry = response.headers.get("Retry-After")
    wait = (
        f"Retry after {retry} seconds."
        if retry and retry.isdigit()
        else "Wait before retrying; the shared web-player quota may take up to an hour to reset."
    )
    return TransientMusicError("Apple Music rate-limited this connection. " + wait)


def status_error(response: httpx.Response) -> MusicError | None:
    code = response.status_code
    other = f"Apple Music returned HTTP {code}. Inspect the resource before retrying a write."
    match code:
        case 429:
            return rate_limited(response)
        case 401 | 403:
            return MusicError(REJECTED)
        case 404:
            return MusicError(NOT_FOUND)
        case _ if 200 <= code < 300:
            return None
        case _ if code >= 500:
            return TransientMusicError(other)
        case _:
            return MusicError(other)


def decode(response: httpx.Response) -> dict:
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise MusicError(
            "Apple Music returned an unreadable response. "
            "Inspect the resource before retrying a write."
        ) from exc


def song(item: dict) -> dict:
    a = item.get("attributes", {})
    play = a.get("playParams", {})
    return {
        "id": item["id"],
        "type": item.get("type", "songs"),
        "source": "web",
        "name": a.get("name"),
        "artist": a.get("artistName"),
        "album": a.get("albumName"),
        "catalog_id": play.get("catalogId")
        or (item["id"] if item.get("type") == "songs" else None),
        "duration_ms": a.get("durationInMillis"),
        "url": a.get("url"),
        "isrc": a.get("isrc"),
        "content_rating": a.get("contentRating"),
    }


def playlist(item: dict) -> dict:
    a = item.get("attributes", {})
    description = a.get("description", {})
    if isinstance(description, dict):
        description = description.get("standard", description.get("short", ""))
    return {
        "id": item["id"],
        "source": "web",
        "name": a.get("name"),
        "description": description,
        "can_edit": a.get("canEdit", False),
        "url": a.get("url"),
    }


def next_offset(data: dict) -> int | None:
    nxt = data.get("next")
    if not nxt:
        return None
    value = parse_qs(urlsplit(nxt).query).get("offset", [None])[0]
    return int(value) if value and value.isdigit() else None


class MusicAPI:
    def __init__(self, credentials: Credentials | None = None, client: httpx.Client | None = None):
        self.credentials = credentials or Credentials()
        self.client = client or httpx.Client(
            timeout=20, headers={"User-Agent": "AppleMusicMCP/0.1"}
        )
        self.storefront = os.environ.get("APPLE_MUSIC_STOREFRONT", "us").lower()
        if not re.fullmatch(r"[a-z]{2}", self.storefront):
            raise MusicError("APPLE_MUSIC_STOREFRONT must be a two-letter country code.")
        self._storefront_resolved = False

    def request(
        self,
        method: str,
        path: str,
        *,
        personal: bool = True,
        web_only: bool = False,
        params: dict | None = None,
        body: dict | None = None,
        missing_ok: bool = False,
    ) -> dict:
        validate_path(path)
        user_token = self.personal_token() if personal else None
        token, web = self.credentials.developer_token(
            self.client,
            force_web=web_only or (personal and self.credentials.user_token_source() == "web"),
        )
        host = WEB_ORIGIN if web else PUBLIC_ORIGIN
        response = self.send(method, host + path, auth_headers(token, user_token), params, body)
        if missing_ok and response.status_code == 404:
            return {}
        error = status_error(response)
        if error is not None:
            raise error
        return decode(response)

    def personal_token(self) -> str:
        token = self.credentials.user_token()
        if not token:
            raise MusicError(NOT_SIGNED_IN)
        return token

    def send(
        self, method: str, url: str, headers: dict, params: dict | None, body: dict | None
    ) -> httpx.Response:
        try:
            return self.client.request(
                method, url, headers=headers, params=params, json=body, follow_redirects=False
            )
        except httpx.HTTPError as exc:
            suffix = UNCERTAIN_WRITE if method != "GET" else ""
            raise TransientMusicError("Could not reach Apple Music." + suffix) from exc

    def resolve_storefront(self) -> str:
        if not self._storefront_resolved and self.credentials.user_token():
            data = self.request("GET", "/v1/me/storefront").get("data", [])
            if data and re.fullmatch(r"[a-z]{2}", data[0].get("id", "")):
                self.storefront = data[0]["id"]
            self._storefront_resolved = True
        return self.storefront

    def search_catalog(self, query: str, kind: str, limit: int, offset: int) -> dict:
        store = self.resolve_storefront()
        result = (
            self.request(
                "GET",
                f"/v1/catalog/{store}/search",
                personal=False,
                params={"term": query, "types": kind, "limit": limit, "offset": offset},
            )
            .get("results", {})
            .get(kind, {})
        )
        items = []
        for item in result.get("data", []):
            if kind == "songs":
                items.append(song(item))
            else:
                a = item.get("attributes", {})
                items.append(
                    {
                        "id": item["id"],
                        "type": kind,
                        "name": a.get("name"),
                        "artist": a.get("artistName"),
                        "url": a.get("url"),
                    }
                )
        return {
            "items": items,
            "offset": offset,
            "next_offset": next_offset(result),
            "storefront": store,
        }

    def search_library(self, query: str, limit: int, offset: int) -> dict:
        if query:
            result = (
                self.request(
                    "GET",
                    "/v1/me/library/search",
                    params={
                        "term": query,
                        "types": "library-songs",
                        "limit": min(limit, 25),
                        "offset": offset,
                    },
                )
                .get("results", {})
                .get("library-songs", {})
            )
        else:
            result = self.request(
                "GET", "/v1/me/library/songs", params={"limit": limit, "offset": offset}
            )
        return {
            "items": [song(i) for i in result.get("data", [])],
            "offset": offset,
            "next_offset": next_offset(result),
        }

    def get_song(self, song_id: str) -> dict:
        if CATALOG_ID.fullmatch(song_id):
            path = f"/v1/catalog/{self.resolve_storefront()}/songs/{song_id}"
            personal = False
        elif LIBRARY_SONG_ID.fullmatch(song_id):
            path, personal = f"/v1/me/library/songs/{song_id}", True
        else:
            raise MusicError("Use a numeric catalog song ID or an i.… library song ID.")
        items = self.request("GET", path, personal=personal).get("data", [])
        if len(items) != 1:
            raise MusicError("Song not found.")
        return song(items[0])

    def list_playlists(self, limit: int, offset: int) -> dict:
        data = self.request(
            "GET", "/v1/me/library/playlists", params={"limit": limit, "offset": offset}
        )
        return {
            "items": [playlist(i) for i in data.get("data", [])],
            "offset": offset,
            "next_offset": next_offset(data),
        }

    def get_playlist(self, playlist_id: str, *, writable: bool = False) -> dict:
        self.validate_playlist_id(playlist_id)
        items = self.request("GET", f"/v1/me/library/playlists/{playlist_id}").get("data", [])
        if len(items) != 1:
            raise MusicError("Playlist not found.")
        value = playlist(items[0])
        if writable and not value["can_edit"]:
            raise MusicError("This playlist is not editable. Choose a playlist you own.")
        return value

    def playlist_tracks(self, playlist_id: str, limit: int, offset: int) -> dict:
        self.validate_playlist_id(playlist_id)
        data = self.request(
            "GET",
            f"/v1/me/library/playlists/{playlist_id}/tracks",
            params={"limit": limit, "offset": offset},
            missing_ok=True,
        )
        if not data:
            # Apple answers an empty playlist's tracks with 404, so only a missing playlist errors.
            self.get_playlist(playlist_id)
        return {
            "items": [song(i) for i in data.get("data", [])],
            "offset": offset,
            "next_offset": next_offset(data),
        }

    def all_playlist_tracks(self, playlist_id: str) -> list[dict]:
        items, offset, visited = [], 0, set()
        while offset not in visited:
            visited.add(offset)
            page = self.playlist_tracks(playlist_id, 100, offset)
            items.extend(page["items"])
            if page["next_offset"] is None:
                return items
            offset = page["next_offset"]
            if len(items) >= 20000:
                raise MusicError("Playlist exceeds the 20,000-track operation limit.")
        raise MusicError("Apple returned repeated playlist pagination; no changes were made.")

    def create_playlist(self, name: str, description: str) -> dict:
        data = self.request(
            "POST",
            "/v1/me/library/playlists",
            body={"attributes": {"name": name, "description": description}},
        )
        items = data.get("data", [])
        if len(items) != 1:
            raise MusicError(
                "Apple accepted creation but did not return a playlist ID. "
                "List playlists before retrying."
            )
        return playlist(items[0])

    def update_playlist(self, playlist_id: str, attributes: dict, dry_run: bool) -> dict:
        before = self.get_playlist(playlist_id, writable=True)
        if dry_run:
            return {"dry_run": True, "before": before, "changes": attributes}
        self.request(
            "PATCH",
            f"/v1/me/library/playlists/{playlist_id}",
            web_only=True,
            body={"attributes": attributes},
        )
        return {"accepted": True, "playlist_id": playlist_id, "changes": attributes}

    def delete_playlist(self, playlist_id: str, dry_run: bool) -> dict:
        before = self.get_playlist(playlist_id, writable=True)
        if dry_run:
            return {"dry_run": True, "playlist": before}
        self.request("DELETE", f"/v1/me/library/playlists/{playlist_id}", web_only=True)
        return {"accepted": True, "deleted": before}

    def add_library(self, song_ids: list[str], dry_run: bool) -> dict:
        self.validate_song_ids(song_ids, catalog_only=True)
        targets = [self.get_song(i) for i in song_ids]
        if dry_run:
            return {"dry_run": True, "adding": targets}
        self.request("POST", "/v1/me/library", params={"ids[songs]": ",".join(song_ids)})
        return {
            "accepted": True,
            "added_catalog_ids": song_ids,
            "note": "Apple accepted the addition; local Music sync can take a moment.",
        }

    def remove_library(self, song_ids: list[str], dry_run: bool) -> dict:
        self.validate_song_ids(song_ids, library_only=True)
        targets = [self.get_song(i) for i in song_ids]
        if dry_run:
            return {
                "dry_run": True,
                "removing": targets,
                "effect": "Music may also remove these songs from playlists and synced devices.",
            }
        removed = []
        try:
            for song_id in song_ids:
                self.request("DELETE", f"/v1/me/library/songs/{song_id}", web_only=True)
                removed.append(song_id)
        except MusicError as exc:
            raise MusicError(f"Accepted removals: {removed}. {exc}") from exc
        return {"accepted": True, "removed_library_ids": removed}

    def add_playlist_tracks(
        self, playlist_id: str, song_ids: list[str], skip_duplicates: bool, dry_run: bool
    ) -> dict:
        self.validate_song_ids(song_ids)
        self.get_playlist(playlist_id, writable=True)
        targets = [self.get_song(i) for i in song_ids]
        before = self.all_playlist_tracks(playlist_id)
        existing = {s["id"] for s in before} | {s["catalog_id"] for s in before if s["catalog_id"]}
        desired = []
        for target in targets:
            identities = {target["id"]}
            if target["catalog_id"]:
                identities.add(target["catalog_id"])
            if not skip_duplicates or not identities.intersection(existing):
                desired.append(target)
                existing.update(identities)
        if dry_run:
            return {"dry_run": True, "adding": desired, "skipped": len(targets) - len(desired)}
        if desired:
            self.request(
                "POST",
                f"/v1/me/library/playlists/{playlist_id}/tracks",
                body={"data": [{"id": s["id"], "type": s["type"]} for s in desired]},
            )
        return {
            "accepted": True,
            "playlist_id": playlist_id,
            "added": [s["id"] for s in desired],
            "skipped": len(targets) - len(desired),
        }

    def remove_playlist_tracks(self, playlist_id: str, song_ids: list[str], dry_run: bool) -> dict:
        self.validate_song_ids(song_ids, library_only=True)
        self.get_playlist(playlist_id, writable=True)
        existing = {s["id"]: s for s in self.all_playlist_tracks(playlist_id)}
        absent = [i for i in song_ids if i not in existing]
        if absent:
            raise MusicError(
                f"Track relationship IDs absent from this playlist: {absent}. "
                "Use IDs from get_playlist_tracks, not catalog search."
            )
        if dry_run:
            return {"dry_run": True, "removing": [existing[i] for i in song_ids]}
        removed = []
        try:
            for song_id in song_ids:
                self.request(
                    "DELETE",
                    f"/v1/me/library/playlists/{playlist_id}/tracks",
                    web_only=True,
                    params={"ids[library-songs]": song_id, "mode": "all"},
                )
                removed.append(song_id)
        except MusicError as exc:
            raise MusicError(f"Accepted removals: {removed}. {exc}") from exc
        return {
            "accepted": True,
            "playlist_id": playlist_id,
            "removed": removed,
            "note": "Removes every occurrence of each supplied relationship ID.",
        }

    def copy_playlist(self, playlist_id: str, name: str) -> dict:
        before = self.get_playlist(playlist_id)
        tracks = self.all_playlist_tracks(playlist_id)
        created = self.create_playlist(name, before.get("description") or "")
        copied = 0
        try:
            for offset in range(0, len(tracks), 100):
                chunk = tracks[offset : offset + 100]
                self.request(
                    "POST",
                    f"/v1/me/library/playlists/{created['id']}/tracks",
                    body={"data": [{"id": s["id"], "type": s["type"]} for s in chunk]},
                )
                copied += len(chunk)
        except MusicError as exc:
            raise MusicError(
                f"Created playlist {created['id']}; {copied} tracks accepted. {exc}"
            ) from exc
        return {"accepted": True, "playlist": created, "copied_tracks": copied}

    @staticmethod
    def validate_playlist_id(value: str) -> None:
        if not PLAYLIST_ID.fullmatch(value):
            raise MusicError("Use a p.… library playlist ID from list_playlists.")

    @staticmethod
    def validate_song_ids(
        values: list[str], *, catalog_only: bool = False, library_only: bool = False
    ) -> None:
        if not 1 <= len(values) <= 100 or len(set(values)) != len(values):
            raise MusicError("Supply 1–100 distinct song IDs.")
        for value in values:
            allowed = (
                CATALOG_ID.fullmatch(value)
                if catalog_only
                else LIBRARY_SONG_ID.fullmatch(value)
                if library_only
                else CATALOG_ID.fullmatch(value) or LIBRARY_SONG_ID.fullmatch(value)
            )
            if not allowed:
                raise MusicError("Invalid song ID. Use IDs returned by this server.")
