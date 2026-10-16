import json

import httpx
import pytest

from apple_music_mcp.api import REJECTED, MusicAPI, next_offset
from apple_music_mcp.auth import Credentials, MusicError, TransientMusicError


class FakeCredentials(Credentials):
    def __init__(self, root):
        super().__init__(root)

    def user_token(self):
        return "private-user-token-do-not-leak"

    def developer_token(self, client, force_web=False):
        return "public-test-token", True


def make_song(song_id="i.one", catalog_id="123"):
    return {
        "id": song_id,
        "type": "library-songs" if song_id.startswith("i.") else "songs",
        "attributes": {
            "name": "Example",
            "artistName": "Artist",
            "albumName": "Album",
            "playParams": {"catalogId": catalog_id},
        },
    }


def make_playlist(editable=True):
    return {"id": "p.test", "attributes": {"name": "Test", "canEdit": editable}}


@pytest.fixture
def api_factory(tmp_path):
    def build(handler):
        return MusicAPI(
            FakeCredentials(tmp_path), httpx.Client(transport=httpx.MockTransport(handler))
        )

    return build


def test_rate_limits_are_errors_not_empty_results(api_factory):
    api = api_factory(lambda request: httpx.Response(429, headers={"Retry-After": "60"}))
    with pytest.raises(MusicError, match="Retry after 60"):
        api.request("GET", "/v1/catalog/us/search", personal=False)


def test_no_token_in_errors_and_no_retry_of_uncertain_write(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        raise httpx.ReadTimeout("secret " + request.headers["Music-User-Token"], request=request)

    api = api_factory(handler)
    with pytest.raises(MusicError, match="outcome is uncertain") as error:
        api.request("POST", "/v1/me/library")
    assert "private-user-token" not in str(error.value)
    assert len(seen) == 1


def test_rejects_arbitrary_hosts_before_sending_credentials(api_factory):
    seen = []
    api = api_factory(lambda request: seen.append(request))
    for path in ["https://evil.example/v1/me/library", "//evil.example/v1/test", "/v1/../test"]:
        with pytest.raises(MusicError, match="Invalid"):
            api.request("GET", path)
    assert seen == []


def test_dry_run_library_add_resolves_songs_without_writes(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("storefront"):
            return httpx.Response(200, json={"data": [{"id": "il"}]})
        return httpx.Response(200, json={"data": [make_song("123")]})

    result = api_factory(handler).add_library(["123"], dry_run=True)
    assert result["adding"][0]["id"] == "123"
    assert all(r.method == "GET" for r in seen)


def test_library_delete_rejects_catalog_ids_without_requests(api_factory):
    seen = []
    api = api_factory(lambda request: seen.append(request))
    with pytest.raises(MusicError, match="Invalid song ID"):
        api.remove_library(["123"], False)
    assert seen == []


def test_protected_playlist_cannot_be_deleted(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": [make_playlist(False)]})

    with pytest.raises(MusicError, match="not editable"):
        api_factory(handler).delete_playlist("p.test", False)
    assert [r.method for r in seen] == ["GET"]


def test_playlist_remove_validates_all_memberships_before_any_delete(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        item = make_song() if request.url.path.endswith("tracks") else make_playlist()
        return httpx.Response(200, json={"data": [item]})

    with pytest.raises(MusicError, match="absent"):
        api_factory(handler).remove_playlist_tracks("p.test", ["i.one", "i.missing"], False)
    assert all(r.method == "GET" for r in seen)


def test_playlist_remove_uses_membership_endpoint_not_library(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        item = make_song() if request.url.path.endswith("tracks") else make_playlist()
        return httpx.Response(200, json={"data": [item]})

    api_factory(handler).remove_playlist_tracks("p.test", ["i.one"], False)
    deletion = next(r for r in seen if r.method == "DELETE")
    assert deletion.url.path == "/v1/me/library/playlists/p.test/tracks"
    assert deletion.url.params["ids[library-songs]"] == "i.one"
    assert deletion.url.params["mode"] == "all"


def test_partial_library_deletion_reports_completed_ids(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        song_id = request.url.path.rsplit("/", 1)[-1]
        if request.method == "GET":
            return httpx.Response(200, json={"data": [make_song(song_id)]})
        return httpx.Response(204 if song_id == "i.one" else 500)

    with pytest.raises(MusicError, match="Accepted removals:.*i.one"):
        api_factory(handler).remove_library(["i.one", "i.two"], False)


def test_catalog_and_library_aliases_do_not_duplicate_playlist_songs(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("storefront"):
            return httpx.Response(200, json={"data": [{"id": "us"}]})
        if request.url.path.endswith("/p.test"):
            data = make_playlist()
        elif request.url.path.endswith("tracks"):
            data = make_song()
        else:
            data = make_song("123")
        return httpx.Response(200, json={"data": [data]})

    result = api_factory(handler).add_playlist_tracks("p.test", ["123"], True, False)
    assert result["skipped"] == 1 and result["added"] == []
    assert all(r.method == "GET" for r in seen)


def test_library_add_sends_documented_catalog_parameter(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        if request.method == "POST":
            return httpx.Response(202)
        data = {"id": "us"} if request.url.path.endswith("storefront") else make_song("123")
        return httpx.Response(200, json={"data": [data]})

    result = api_factory(handler).add_library(["123"], False)
    assert result["accepted"]
    post = next(r for r in seen if r.method == "POST")
    assert post.url.path == "/v1/me/library"
    assert post.url.params["ids[songs]"] == "123"


def test_duplicate_aliases_in_one_batch_are_skipped(api_factory):
    posted = []

    def handler(request):
        if request.method == "POST":
            posted.extend(json.loads(request.content)["data"])
            return httpx.Response(204)
        if request.url.path.endswith("storefront"):
            return httpx.Response(200, json={"data": [{"id": "us"}]})
        if request.url.path.endswith("/p.test"):
            data = [make_playlist()]
        elif request.url.path.endswith("tracks"):
            data = []
        elif request.url.path.endswith("i.one"):
            data = [make_song("i.one", "123")]
        else:
            data = [make_song("123", "123")]
        return httpx.Response(200, json={"data": data})

    result = api_factory(handler).add_playlist_tracks("p.test", ["123", "i.one"], True, False)
    assert result["added"] == ["123"] and result["skipped"] == 1
    assert len(posted) == 1


def test_playlist_copy_preserves_pagination_order(api_factory):
    seen = []

    def handler(request):
        seen.append(request)
        if request.method == "POST":
            if request.url.path.endswith("playlists"):
                return httpx.Response(201, json={"data": [{**make_playlist(), "id": "p.copy"}]})
            return httpx.Response(204)
        if request.url.path.endswith("tracks"):
            if request.url.params.get("offset") == "0":
                return httpx.Response(
                    200,
                    json={
                        "data": [make_song("i.one")],
                        "next": "/v1/me/library/playlists/p.test/tracks?offset=1",
                    },
                )
            return httpx.Response(200, json={"data": [make_song("i.two")]})
        return httpx.Response(200, json={"data": [make_playlist()]})

    result = api_factory(handler).copy_playlist("p.test", "Copy")
    posts = [
        json.loads(r.content) for r in seen if r.method == "POST" and r.url.path.endswith("tracks")
    ]
    assert [i["id"] for i in posts[0]["data"]] == ["i.one", "i.two"]
    assert result["copied_tracks"] == 2


def test_repeated_pagination_raises_instead_of_returning_partial_playlist(api_factory):
    def handler(request):
        return httpx.Response(
            200,
            json={"data": [make_song()], "next": "/v1/me/library/playlists/p.test/tracks?offset=0"},
        )

    with pytest.raises(MusicError, match="repeated"):
        api_factory(handler).all_playlist_tracks("p.test")


def test_next_offset():
    assert next_offset({"next": "/v1/me/library/songs?offset=100&limit=100"}) == 100
    assert next_offset({}) is None


def routed(*table):
    """Answer each request from the first (method, path-suffix, respond) row that matches."""

    def handler(request):
        for method, suffix, respond in table:
            if request.method == method and request.url.path.endswith(suffix):
                return respond(request)
        raise AssertionError(f"Unexpected {request.method} {request.url.path}")

    return handler


def answer(status, data=None):
    return lambda request: httpx.Response(status, json=None if data is None else {"data": data})


def test_adding_songs_to_an_empty_playlist_posts_them(api_factory):
    posted = []

    def accept(request):
        posted.extend(json.loads(request.content)["data"])
        return httpx.Response(204)

    api = api_factory(
        routed(
            ("POST", "/tracks", accept),
            ("GET", "/storefront", answer(200, [{"id": "us"}])),
            ("GET", "/tracks", answer(404)),
            ("GET", "/p.test", answer(200, [make_playlist()])),
            ("GET", "/123", answer(200, [make_song("123")])),
        )
    )
    result = api.add_playlist_tracks("p.test", ["123"], True, False)
    assert result["added"] == ["123"]
    assert posted == [{"id": "123", "type": "songs"}]


def test_empty_playlist_reads_as_an_empty_page(api_factory):
    api = api_factory(
        routed(("GET", "/tracks", answer(404)), ("GET", "/p.test", answer(200, [make_playlist()])))
    )
    assert api.playlist_tracks("p.test", 100, 0) == {"items": [], "offset": 0, "next_offset": None}


def test_tracks_of_a_missing_playlist_is_still_an_error(api_factory):
    api = api_factory(routed(("GET", "", answer(404))))
    with pytest.raises(MusicError, match="could not find"):
        api.playlist_tracks("p.gone", 100, 0)


def test_server_errors_are_transient_and_client_errors_are_not(api_factory):
    with pytest.raises(TransientMusicError, match="HTTP 503"):
        api_factory(routed(("GET", "", answer(503)))).request(
            "GET", "/v1/catalog/us/search", personal=False
        )
    with pytest.raises(MusicError, match="HTTP 400") as error:
        api_factory(routed(("GET", "", answer(400)))).request(
            "GET", "/v1/catalog/us/search", personal=False
        )
    assert not isinstance(error.value, TransientMusicError)


def test_rate_limit_is_transient(api_factory):
    api = api_factory(routed(("GET", "", lambda r: httpx.Response(429))))
    with pytest.raises(TransientMusicError, match="rate-limited"):
        api.request("GET", "/v1/catalog/us/search", personal=False)


class SwitchableCredentials(FakeCredentials):
    def __init__(self, root, token):
        super().__init__(root)
        self.token = token

    def user_token(self):
        return self.token


def test_stale_sign_in_does_not_break_catalog_search(api_factory, monkeypatch):
    monkeypatch.delenv("APPLE_MUSIC_STOREFRONT", raising=False)
    searched = []

    def search(request):
        searched.append(request.url.path)
        return httpx.Response(200, json={"results": {"songs": {"data": [make_song("123")]}}})

    api = api_factory(routed(("GET", "/storefront", answer(401)), ("GET", "/search", search)))
    result = api.search_catalog("Daft Punk", "songs", 10, 0)
    assert result["storefront"] == "us" and len(result["items"]) == 1
    assert searched == ["/v1/catalog/us/search"]


def test_storefront_follows_the_signed_in_account(tmp_path, monkeypatch):
    monkeypatch.delenv("APPLE_MUSIC_STOREFRONT", raising=False)
    stores = {"a" * 40: "us", "b" * 40: "il"}

    def storefront(request):
        store = stores[request.headers["Music-User-Token"]]
        return httpx.Response(200, json={"data": [{"id": store}]})

    credentials = SwitchableCredentials(tmp_path, "a" * 40)
    transport = httpx.MockTransport(routed(("GET", "/storefront", storefront)))
    api = MusicAPI(credentials, httpx.Client(transport=transport))
    assert api.resolve_storefront() == "us"
    credentials.token = "b" * 40
    assert api.resolve_storefront() == "il"
    credentials.token = None
    assert api.resolve_storefront() == "us"


def test_strict_storefront_lookup_reports_a_rejected_token(api_factory):
    api = api_factory(routed(("GET", "/storefront", answer(401))))
    with pytest.raises(MusicError, match="rejected access"):
        api.resolve_storefront(strict=True)


def test_check_access_reports_errors_without_raising(api_factory):
    api = api_factory(routed(("GET", "/storefront", answer(401))))
    assert api.check_access() == {"web_accessible": False, "web_error": REJECTED}


def test_rejected_web_player_token_is_dropped_for_a_fresh_fetch(tmp_path):
    (tmp_path / "web-token.json").write_text('{"token": "cached"}')
    transport = httpx.MockTransport(answer(401))
    api = MusicAPI(FakeCredentials(tmp_path), httpx.Client(transport=transport))
    with pytest.raises(MusicError, match="rejected access"):
        api.request("GET", "/v1/me/library/songs")
    assert not (tmp_path / "web-token.json").exists()


def test_explicit_developer_token_rejection_keeps_the_web_cache(tmp_path, monkeypatch):
    (tmp_path / "web-token.json").write_text('{"token": "cached"}')
    credentials = FakeCredentials(tmp_path)
    monkeypatch.setattr(
        credentials, "developer_token", lambda client, force_web=False: ("x", False)
    )
    api = MusicAPI(credentials, httpx.Client(transport=httpx.MockTransport(answer(403))))
    with pytest.raises(MusicError, match="rejected access"):
        api.request("GET", "/v1/me/library/songs")
    assert (tmp_path / "web-token.json").exists()
