# Apple Music MCP Server

Manage Apple Music from Hermes, ChatGPT, or another MCP client using **Python**
and **FastMCP 3**. Search the catalog and your library, add or remove songs, and
create, edit, copy, and organize playlists through 17 tools.

The server runs locally over **stdio**. Hermes launches it directly; ChatGPT
connects through OpenAI's private Secure MCP Tunnel.

## Requirements

- Python 3.11 or newer.
- An Apple Music account and active subscription for personal library operations.
- A browser for the one-time Apple Music sign-in.
- macOS and the Music app for native operations such as playlist reordering and
  importing local audio. Web operations do not require the native Music app.

No Apple developer account is needed for the default browser sign-in. The default
backend uses Apple's web player and some **undocumented endpoints**; it can change
when Apple changes its player. This project is an independent integration.

## Install

Clone this repository and open its directory, then run:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[browser]'
```

The sign-in helper uses Google Chrome when installed. Otherwise, install its
Chromium browser:

```bash
.venv/bin/python -m playwright install chromium
```

Commands use macOS/Linux virtual environment paths. On Windows, use
`.venv/Scripts/python.exe` instead. The native backend and Keychain/background
helpers require macOS.

## Sign in to Apple Music

```bash
.venv/bin/apple-music-mcp login --web
.venv/bin/apple-music-mcp status
```

Complete Apple's sign-in and verification in the browser. The helper verifies
library access before saving the music token. Passwords and verification codes
stay in Apple's sign-in flow. Its temporary browser profile is deleted afterward.

The saved token is stored in `~/.config/apple-music-mcp/credentials.json`,
with private file permissions. Set `APPLE_MUSIC_MCP_HOME` to use another directory.
Do not commit that directory or any tokens.

If upgrading from an installation that used a different credential directory,
set `APPLE_MUSIC_MCP_HOME` to that existing directory before starting the server,
or sign in again. Recreate tunnel profiles and reinstall the background service
when moving to the generic runtime paths and service identifiers below.

An MCP client can also call `connect_apple_music`. It returns immediately while
`get_status` reports sign-in progress. Keep its server alive until sign-in finishes.
Concurrent clients reuse one sign-in flow.

For native Music.app access, run:

```bash
.venv/bin/apple-music-mcp status --native
```

Allow the calling app to control Music when macOS requests it. Music must be signed
in and its library available. Access is managed under **System Settings → Privacy
& Security → Automation**.

## Connect to Hermes

Use the absolute path to your checkout's Python executable in Hermes's MCP config:

```yaml
mcp_servers:
  apple_music:
    command: /absolute/path/apple-music-mcp-server/.venv/bin/python
    args: [-m, apple_music_mcp, serve]
    cwd: /absolute/path/apple-music-mcp-server
    env:
      APPLE_MUSIC_STOREFRONT: il
    enabled: true
    supports_parallel_tool_calls: false
```

`il` is the Israel storefront. Set your preferred storefront for catalog searches;
the signed-in account's storefront is detected for personal operations.

Reload the client's MCP connections, enable the discovered tools, and check with
`hermes mcp test apple_music`. Then ask naturally:

> Find “Get Lucky” by Daft Punk and add the album version to my library.

> Create a playlist called Evening and add these songs to it.

> Remove this song from Evening but keep it in my library.

Hermes manages the server process in the background; no separate server Terminal
is needed while Hermes is running.

## Other MCP clients

Configure the same stdio command and arguments in your client's MCP settings:

```json
{
  "mcpServers": {
    "apple_music": {
      "command": "/absolute/path/apple-music-mcp-server/.venv/bin/python",
      "args": ["-m", "apple_music_mcp", "serve"]
    }
  }
}
```

## Connect to ChatGPT

Use [OpenAI's Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
to reach the local stdio server without exposing a public endpoint. The local
`tunnel-client` must stay running for discovery and tool calls.

1. Download the official tunnel client from OpenAI's guide or Platform tunnel
   settings and verify its published checksum.
2. Create a tunnel associated with the intended ChatGPT workspace and Platform
   organization. Creating it requires **Tunnels Read + Manage**.
3. Create a runtime API key with **Tunnels Read + Use**.
4. Configure the tunnel to launch your absolute Python path with
   `-m apple_music_mcp serve`, then run the client.
5. In ChatGPT's custom MCP setup, choose **Tunnel**, select its ID, and register
   and connect **My Apple Music**. The tunnel authenticates through your OpenAI
   organization/workspace. Review the access before connecting.

`scripts/connect_chatgpt.py` targets an installed runtime at
`~/.local/share/apple-music-mcp/.venv` and the official client at
`.chatgpt/tunnel-client` in this checkout. Install the package at that runtime
path first to use the helper:

```bash
python3 -m venv ~/.local/share/apple-music-mcp/.venv
~/.local/share/apple-music-mcp/.venv/bin/python -m pip install '.[browser]'
# Place the verified official client at .chatgpt/tunnel-client first.
~/.local/share/apple-music-mcp/.venv/bin/python scripts/connect_chatgpt.py
```

It asks for the tunnel ID and key locally. The foreground helper does not save
the OpenAI key; keep its Terminal open. Apple Music credentials remain local.

For macOS automatic login startup without a Terminal window, see
[the background service setup](docs/background-service.md). That service stores
its runtime key in macOS Keychain. Your Mac must remain awake and online.

## Tools

Ask for music actions normally; the agent chooses the tools. If account access is
missing, the agent can call `connect_apple_music` to open Apple's sign-in on this
Mac. It returns immediately, while `get_status` reports progress and verifies
library access. Complete sign-in in the browser, then the agent can continue the
requested edit. No terminal command or MCP server name is needed in your request.
The MCP process must stay running until sign-in finishes. Concurrent clients reuse
one sign-in flow; shutting down its owner cancels it and cleans the browser profile.

| Tool | Purpose |
| --- | --- |
| `get_status` | Check sign-in and optional native automation access |
| `connect_apple_music` | Start human-completed Apple Music sign-in in a local browser |
| `search_music` | Search catalog songs, albums, artists, or playlists |
| `search_library` | Search or browse your songs |
| `get_song_details` | Look up one exact catalog/library song |
| `add_songs_to_library` | Add catalog songs to your library |
| `remove_songs_from_library` | Remove exact library songs |
| `list_playlists` | List your playlists and their IDs |
| `get_playlist_tracks` | Read ordered playlist membership |
| `create_playlist` | Create a playlist |
| `update_playlist` | Rename or change its description |
| `delete_playlist` | Delete an editable playlist |
| `add_songs_to_playlist` | Append songs, skipping duplicates by default |
| `remove_songs_from_playlist` | Remove playlist membership, keeping library songs |
| `duplicate_playlist` | Copy ordered playlist contents |
| `reorder_playlist` | Reorder a native Music.app playlist with a recovery copy |
| `import_audio_files` | Import local audio into Music.app |

Search and list tools return `next_offset` when another page is available. Pass that
value back as `offset`. Mutations accept at most 100 songs per call. Use `dry_run=true`
to preview additions, removals, or updates before changing anything.

The default backend is web when signed in, otherwise native. Choose `backend="native"`
on `search_library`, `list_playlists`, or `create_playlist` when needed. Catalog search
always uses Apple’s online catalog. The user's storefront is detected after sign-in;
Hermes uses Israel (`il`) for unauthenticated catalog search on this installation.

### IDs matter

- Numeric IDs: catalog songs, returned by `search_music`.
- `i.…`: web library songs or playlist membership, returned by library/playlist reads.
- `p.…`: web library playlists.
- 16 hexadecimal characters: native Music.app persistent IDs.

Use the IDs returned by the matching backend. Playlist removals require IDs from
`get_playlist_tracks`, not catalog search. Library removals require IDs from
`search_library`, not a playlist relationship. A removal deletes every occurrence
of the supplied membership ID from that playlist.

Removing a song from your **library** can also remove it from playlists and synced
devices, according to Apple's current behavior and your settings. Removing it from
a **playlist** keeps the library song. Adding catalog songs to a playlist does not
explicitly add them to your library; Apple Music's playlist settings may do so.
Smart, special, and non-editable playlists are rejected for edits.

Web writes report `accepted` after an Apple success response, because library/device
sync is asynchronous. Native writes read back the resulting state. A failed or timed
out write is never automatically retried. If a partial batch succeeds, its completed IDs are included in the error, on the web and
native backends alike; read the resource before retrying. Native imports report how many
files Music did not confirm as `unconfirmed`. Reordering checks
that every existing occurrence is retained and saves a recovery playlist before
rewriting; if verification fails, that recovery copy remains in Music.

## Configuration

| Variable | Purpose |
| --- | --- |
| `APPLE_MUSIC_MCP_HOME` | Override the local credential/settings directory |
| `APPLE_MUSIC_STOREFRONT` | Catalog storefront when no signed-in storefront is available |
| `APPLE_MUSIC_DEVELOPER_TOKEN` | Supply your own Apple Music developer token |
| `APPLE_MUSIC_USER_TOKEN` | Supply an existing music user token instead of the saved token |

`APPLE_MUSIC_USER_TOKEN` can supply an existing music token instead of the saved token;
while it is set, `connect_apple_music` refuses to start, because a new sign-in could
never take effect. `get_status` reports `token_from_environment`.

Keep tokens in your local environment or credential store. Do not put them in MCP
configuration committed to this repository.

The native backend is a fixed JXA program called by Python with JSON arguments;
user strings are never interpolated into executable source. On macOS, concurrent
Hermes and ChatGPT processes share a local edit lock so music mutations do not overlap.

## Development

```bash
.venv/bin/python -m pip install -e '.[dev,browser]'
.venv/bin/pytest -q
.venv/bin/ruff check src scripts tests
.venv/bin/ruff format --check src scripts tests
```

`requirements.lock` and `requirements-browser.lock` capture the original tested
Python environment. For a matching environment, install the appropriate lock file
and then install this package with `--no-deps -e .`.

Tests cover IDs, protected playlists, dry runs, pagination, duplicate detection,
partial failures, timeouts, credential handling, sign-in callbacks, tool schemas,
edit locking, and background startup behavior. They do not modify a real music
library. Some tests bind temporary localhost ports.

## Project layout

```text
src/apple_music_mcp/    FastMCP server, Apple web API, native bridge, sign-in helpers
scripts/               ChatGPT tunnel and macOS background service helpers
tests/                 Automated tests
docs/                  Background service installation guide
```

The repository excludes credentials, API keys, browser profiles, logs, screenshots,
virtual environments, and the vendor tunnel binary.

## References

Sources: [FastMCP tools](https://gofastmcp.com/servers/tools),
[Apple Music API](https://developer.apple.com/documentation/applemusicapi),
[MusicKit authentication](https://developer.apple.com/documentation/applemusicapi/user-authentication-for-musickit).
The web-player endpoint behavior was checked against the maintainer's
[Apple Music MCP implementation](https://github.com/epheterson/applemusic-mcp/blob/main/src/applemusic_mcp/amp_api.py).
Direct web sign-in follows the token mechanism in its
[browser authentication implementation](https://github.com/epheterson/applemusic-mcp/blob/main/src/applemusic_mcp/browser.py).
