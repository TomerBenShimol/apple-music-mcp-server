# Apple Music MCP Server

![Platform: macOS](https://img.shields.io/badge/platform-macOS-black)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)
![Built with FastMCP 3](https://img.shields.io/badge/built_with-FastMCP_3-6E56CF)
![Transport: stdio](https://img.shields.io/badge/transport-stdio-00897B)

Connect Apple Music to your favorite AI client and ask it to manage your music.
Find a song, add it to your library, or put a playlist together without leaving
your conversation.

This is a local MCP server built with Python and FastMCP, with 17 tools for catalog
search, library edits, and playlists. Install it on your Mac and sign in to your
own Apple Music account.

> Find the album version of “Get Lucky” by Daft Punk and add it to my library.

> Create a playlist called Evening with these songs, skipping duplicates.

> Remove this song from Evening, but keep it in my library.

Your client starts the server on your Mac when it connects. You don't need to
keep a separate Terminal window open after setup, or install Docker or Linux.
There's no server to host.

[Quick start](#quick-start) · [Client installation](#client-installation) ·
[Tools](#tools) · [Configuration](#configuration) ·
[Troubleshooting](#troubleshooting) · [Development](#development)

## Features

- Search Apple's catalog for songs, albums, artists, and playlists.
- Browse your library, look up song details, and add or remove songs.
- Create playlists, change their names or descriptions, copy them, edit their tracks,
  or delete them.
- Reorder playlists and import local audio through Music.app.
- Use the same saved sign-in across your configured clients.

The setup commands can write your client settings or print configuration for you
to copy. They check for conflicts and back up existing settings before changing
them. You can also check dependencies and tool discovery before opening a client.

This project is independent of Apple. The default browser sign-in works without
an Apple developer account. It relies on Apple's web player and some undocumented
endpoints, so Apple changes can break it.

## Requirements

| Requirement | Details |
| --- | --- |
| macOS | This guide is for Macs; Music.app automation also requires macOS |
| Python 3.11+ | Run `python3 --version` to check your version |
| Git | Used to clone the repository |
| Apple Music account | You need an active subscription to work with your personal library |
| Browser | Google Chrome, or Playwright Chromium using the command below |
| MCP client | Your coding agent or desktop client needs to be installed already |
| Internet access | Used for sign-in, catalog searches, and online library access |

For playlist reordering and local audio imports, sign in to Music.app as well.
If you're using another operating system, read the
[compatibility notes](docs/clients.md#compatibility-boundaries).

## Quick start

### 1. Clone and install

Open Terminal and check that `python3` is version 3.11 or newer, then run:

```bash
git clone https://github.com/TomerBenShimol/apple-music-mcp-server.git
cd apple-music-mcp-server
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[browser]'
```

Sign-in uses Google Chrome if it's installed. If you don't have Chrome, install
Playwright's Chromium browser:

```bash
.venv/bin/python -m playwright install chromium
```

Run the remaining commands from this repository's directory. They use the virtual
environment directly, so you don't have to activate it or install anything globally.
Keep the repository and `.venv` where they are once you've connected your clients:
their settings will point to those exact paths.

### 2. Sign in to Apple Music

```bash
.venv/bin/apple-music-mcp login --web
.venv/bin/apple-music-mcp status
```

Finish signing in with Apple in the browser window, including any verification
step. The helper checks that it can access your library before saving the music
token. Look for `"web_accessible": true` in the status output.

You enter your Apple password and verification codes only in Apple's sign-in flow.
The helper deletes its temporary browser profile when sign-in ends and saves your
music credentials in `~/.config/apple-music-mcp/credentials.json` on your Mac,
with private file permissions.

### 3. Connect your client

Quit the client you want to connect, then run its install command:

```bash
# Choose your client:
.venv/bin/apple-music-mcp install claude-code
# .venv/bin/apple-music-mcp install claude-desktop
# .venv/bin/apple-music-mcp install codex
# .venv/bin/apple-music-mcp install gemini-cli
# .venv/bin/apple-music-mcp install cursor
# .venv/bin/apple-music-mcp install vscode
```

Reopen your client and approve the Apple Music server when it asks. You may need
to reload its MCP connections before the tools appear. Each client has its own
command and settings path under [client installation](#client-installation).

### 4. Verify and try it

```bash
.venv/bin/apple-music-mcp doctor --probe
```

Under `mcp_probe`, look for `"status": "ready"` and `"tool_count": 17`.
That confirms the local server can start and list its tools. Use `status` to check
your Apple Music account access.

Ask your agent:

> Check my Apple Music connection and find songs by Daft Punk.

Once that works, ask for a library or playlist edit in your own words. Your agent
chooses the tools; you don't have to name them. If you need to sign in again, it
can open the browser with `connect_apple_music` and check progress with `get_status`.
Leave your client running until sign-in finishes.

## Client installation

The commands below add the server to your client's user settings. They leave your
other settings alone and save a private backup beside an existing file before
updating it. Running the same install again won't change anything. If there's
already a different `apple-music` entry, the installer stops with an error so you
can resolve it.

| Client | Installer target | Default macOS user configuration |
| --- | --- | --- |
| [Claude Code](#claude-code) | `claude-code` | `~/.claude.json` |
| [Claude Desktop](#claude-desktop) | `claude-desktop` | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| [Codex](#codex) | `codex` | `~/.codex/config.toml`, or `$CODEX_HOME/config.toml` |
| [Gemini CLI](#gemini-cli) | `gemini-cli` | `~/.gemini/settings.json` |
| [Cursor](#cursor) | `cursor` | `~/.cursor/mcp.json` |
| [VS Code](#vs-code) | `vscode` | `~/Library/Application Support/Code/User/mcp.json` |

The configuration formats and installers have automated tests. Testing inside
every client app is still on the to-do list. You'll need to install the client
itself and approve the tools there.

### Claude Code

```bash
.venv/bin/apple-music-mcp install claude-code
```

Restart Claude Code and approve the server when asked. To add it to one project:

```bash
.venv/bin/apple-music-mcp install claude-code --scope project --project-dir /absolute/path/to/project
```

That writes `.mcp.json` in the project you selected.

### Claude Desktop

```bash
.venv/bin/apple-music-mcp install claude-desktop
```

Quit and reopen Claude Desktop to load the settings. This uses Claude's local MCP
configuration. There isn't a desktop extension bundle yet.

### Codex

```bash
.venv/bin/apple-music-mcp install codex
```

Restart Codex to load the TOML settings. If you've set `CODEX_HOME`, the installer
uses it. To keep the connection in one project, add
`--scope project --project-dir /absolute/path/to/project`. This writes
`.codex/config.toml` inside that project.

### Gemini CLI

```bash
.venv/bin/apple-music-mcp install gemini-cli
```

Restart Gemini CLI and approve the connection when asked. For a single project,
add `--scope project --project-dir /absolute/path/to/project`. The installer will
write `.gemini/settings.json` there.

### Cursor

```bash
.venv/bin/apple-music-mcp install cursor
```

Restart Cursor or reload its MCP connections, then enable the server if asked.
To use project settings, add `--scope project --project-dir /absolute/path/to/project`.
That writes `.cursor/mcp.json` in your project.

### VS Code

```bash
.venv/bin/apple-music-mcp install vscode
```

Reload VS Code, then start and approve the server when asked. For one workspace:

```bash
.venv/bin/apple-music-mcp install vscode --scope project --project-dir /absolute/path/to/project
```

That writes `.vscode/mcp.json`. If you use another editor profile or installation,
point the installer at its settings with `--config-file /absolute/path/to/mcp.json`.

### Preview or configure manually

To see what an installer would add without changing your settings:

```bash
.venv/bin/apple-music-mcp install claude-code --dry-run
```

To copy the settings yourself, use the configuration command. Replace `claude-code`
with the client you want:

```bash
.venv/bin/apple-music-mcp config claude-code
.venv/bin/apple-music-mcp clients
```

You'll get TOML for Codex and JSON for the other clients. The output includes the
full path to your virtual environment's Python and your credential directory.
It doesn't copy tokens into the client's settings.

If your settings use JSON comments, trailing commas, duplicate keys, symbolic
links, or a TOML structure the installer can't safely extend, it leaves the file
alone. Use `config` and merge the output yourself. The
[client setup guide](docs/clients.md) covers other paths and checks to run afterward.

### Other MCP clients

For another stdio client, start with:

```bash
.venv/bin/apple-music-mcp config generic
```

The command fills in your paths in an entry like this:

```json
{
  "mcpServers": {
    "apple-music": {
      "command": "/absolute/path/apple-music-mcp-server/.venv/bin/python",
      "args": ["-m", "apple_music_mcp", "serve"],
      "env": {
        "APPLE_MUSIC_MCP_HOME": "/absolute/path/to/credentials-directory"
      }
    }
  }
}
```

Check your client's documentation for the right root structure. This server uses
local stdio, so a cloud application needs a way to reach your Mac.

### ChatGPT

ChatGPT connects through OpenAI's private Secure MCP Tunnel, which needs to keep
running on your Mac. Follow the [ChatGPT connection guide](docs/chatgpt.md);
[macOS background startup](docs/background-service.md) is available if you want it
to start at login.

ChatGPT has its own setup, separate from the six local client installers. There
isn't a hosted HTTP deployment or a one-click plugin package in this install flow.

## Tools

| Tool | Purpose |
| --- | --- |
| `get_status` | Check sign-in, and optionally permission to control Music.app |
| `connect_apple_music` | Open a local browser so you can sign in with Apple |
| `search_music` | Search catalog songs, albums, artists, or playlists |
| `search_library` | Find songs in your library or browse them |
| `get_song_details` | Look up a specific song in the catalog or your library |
| `add_songs_to_library` | Add catalog songs to your library |
| `remove_songs_from_library` | Remove specific songs from your library |
| `list_playlists` | List your playlists and their IDs |
| `get_playlist_tracks` | Get the songs in a playlist, in order |
| `create_playlist` | Create a playlist |
| `update_playlist` | Rename a playlist or change its description |
| `delete_playlist` | Delete an editable playlist |
| `add_songs_to_playlist` | Add songs at the end, skipping duplicates by default |
| `remove_songs_from_playlist` | Take songs out of a playlist and keep them in your library |
| `duplicate_playlist` | Copy a playlist into a new one, keeping the song order |
| `reorder_playlist` | Change the order of a Music.app playlist and keep a recovery copy |
| `import_audio_files` | Import local audio files into Music.app |

### Music.app access

To reorder a playlist or import local audio, the server needs access to Music.app.
Check it with:

```bash
.venv/bin/apple-music-mcp status --native
```

When macOS asks, allow the app running the server to control Music. You can check
this later in System Settings → Privacy & Security → Automation. Your agent can
also call `get_status(check_native=true)`. A permission you granted to Terminal
may not cover your client app.

By default, the server uses web access if you're signed in and native access
otherwise. You can choose Music.app explicitly with `backend="native"` on
`search_library`, `list_playlists`, and `create_playlist`. Catalog searches always
use Apple's online catalog.

### IDs, pagination, and edits

- Catalog songs have numeric IDs from `search_music`. Use those when adding to your library.
- Web library songs and playlist memberships have `i.…` IDs from the matching read tool.
- Web library playlists have `p.…` IDs.
- Native Music.app objects have 16-character hexadecimal persistent IDs.

Keep IDs with the backend they came from. To remove a library song, use the ID
from `search_library`. To remove it from a playlist, use the membership ID from
`get_playlist_tracks`. Removing a playlist membership deletes every occurrence
of that membership ID.

If a search or list response includes `next_offset`, pass that value as `offset`
to get the next page. Additions and removals take up to 100 song IDs per call.
Reordering takes the full playlist order, including duplicates, up to 20,000 IDs.
Audio imports take up to 25 file paths.

You can preview an edit with `dry_run` on tools that support it. Playlist creation
and duplication don't have a preview option.

Removing a song from your library can also remove it from playlists and synced
devices. Removing it from a playlist keeps it in your library. Adding songs to a
playlist doesn't explicitly add them to your library, although your Apple Music
settings may do that. The server won't edit smart, special, or non-editable playlists.

For web edits, `accepted` means Apple accepted the request; syncing may still be
in progress. Native edits read back the result. The server won't automatically
retry a failed or timed-out edit. If only part of a batch succeeds, the error lists
the completed IDs. Check the affected library or playlist before trying again.

Native imports report files Music.app didn't confirm as `unconfirmed`. Playlist
reordering keeps every existing song occurrence and creates a recovery playlist.
If the result can't be verified, that copy stays available.

## Configuration

| Environment variable | Purpose |
| --- | --- |
| `APPLE_MUSIC_MCP_HOME` | Credential/settings directory; default `~/.config/apple-music-mcp` |
| `APPLE_MUSIC_STOREFRONT` | Catalog region before a signed-in storefront is available; default `us` |
| `APPLE_MUSIC_DEVELOPER_TOKEN` | Optional Apple Music developer token |
| `APPLE_MUSIC_USER_TOKEN` | Optional existing music token, overriding the saved token |

Your account's storefront is detected for personal library operations. To choose
a region for catalog searches when installing a client:

```bash
.venv/bin/apple-music-mcp install cursor --storefront gb
```

Set these options on your first install. If you've already installed an entry
with different settings, edit that entry or pick another `--name`.

If you want to save credentials elsewhere, use the same directory for sign-in
and client setup:

```bash
APPLE_MUSIC_MCP_HOME="$HOME/.config/apple-music-work" .venv/bin/apple-music-mcp login --web
.venv/bin/apple-music-mcp install codex --name apple-music-work --data-dir "$HOME/.config/apple-music-work"
```

If an older installation saved credentials elsewhere, pass that directory's full
path to `--data-dir` or sign in again. If you move the repository or virtual
environment, update the Python path in your client's settings.

### Credentials and local processes

Keep tokens in your local credential store or environment. Don't commit them in
client settings. Generated configurations contain paths and an optional storefront.
Settings backups can contain credentials from other integrations, so keep those
private too.

If you've set `APPLE_MUSIC_USER_TOKEN`, `connect_apple_music` won't start another
sign-in: that environment value would override the new token. You can see this
in the `token_from_environment` field returned by `get_status`.

On macOS, server processes share a local lock to keep music edits from overlapping.
Clients also reuse a sign-in flow if one is already running. For Music.app calls,
the native bridge passes JSON arguments to a fixed JXA program. It doesn't insert
user text into executable source.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Python installation fails | Run `python3 --version`. You need Python 3.11 or newer |
| Sign-in cannot open a browser | Install the `[browser]` extra, then make sure you have Chrome or Playwright Chromium |
| Tools do not appear in the client | Reopen the client or reload MCP, then approve the server. Check that you're using the right profile and that your organization allows it |
| Server cannot start | Run `doctor --probe` and check that the Python path in your settings still exists |
| Account is disconnected | Run `status` followed by `login --web`, or ask your agent to connect Apple Music |
| Music.app access is denied | Check that you're signed in to Music.app and that the app running the server has Automation permission |
| Installer rejects an existing entry | Edit that entry or choose another `--name`. Use `config` if you want to merge settings yourself |
| Installer cannot parse settings | If the file has comments, trailing commas, or unsupported TOML, merge the settings yourself |
| An edit times out or partly succeeds | Check the library or playlist before trying the edit again |

To check your setup:

```bash
.venv/bin/apple-music-mcp doctor
.venv/bin/apple-music-mcp doctor --probe
.venv/bin/apple-music-mcp status
```

Use `doctor` for local dependency checks. It doesn't read your tokens or contact
Apple. With `doctor --probe`, it also starts a temporary server and lists the tools
without calling them or changing your library. Use `status` to check account access
with Apple. You'll still need to check the browser and Automation permissions
separately; `doctor` reports those as unchecked.

If you open an issue, include your macOS, Python, and client versions, along with
the command you ran and the error. Check logs and diagnostics for private paths or
account data before posting them. Don't share tokens or `credentials.json`.

## Updating and removing

Stop your clients' connections before updating, then run:

```bash
git pull --ff-only
.venv/bin/python -m pip install -e '.[browser]'
.venv/bin/apple-music-mcp doctor --probe
```

Reopen your clients afterward. You only need to reinstall their settings if the
Python or credential paths have changed.

To disconnect a client, remove its `apple-music` entry from the settings file listed
above and reload the client. After disconnecting all clients, you can delete the
repository and virtual environment. If you also want to remove the saved music
token, run this first:

```bash
.venv/bin/apple-music-mcp logout
```

`logout` removes locally saved tokens. It won't change a token supplied through
your environment, and it doesn't guarantee that Apple revokes the account's
authorization. If you set up the ChatGPT background service, follow its
[removal instructions](docs/background-service.md) as well.

## Development

```bash
.venv/bin/python -m pip install -e '.[dev,browser]'
.venv/bin/pytest -q
.venv/bin/ruff check src scripts tests
.venv/bin/ruff format --check src scripts tests
```

Tests cover tool schemas, IDs, protected playlists, dry runs, pagination, duplicate
detection, partial failures, timeouts, credentials, sign-in, process locking, client
settings, and background startup. They don't modify a real music library. Some
need to bind temporary localhost ports. Client format tests and the MCP probe
check the server and settings; testing inside each client app is a separate step.

To reproduce the original tested Python environment, install
`requirements.lock` or `requirements-browser.lock`, then install this package
with `--no-deps -e .`.

```text
src/apple_music_mcp/    FastMCP tools, web API, native bridge, sign-in, and client setup
scripts/               Optional ChatGPT tunnel and macOS service helpers
tests/                 Automated tests
docs/                  Client setup, ChatGPT connection, and background service guides
```

The repository's ignore rules exclude credentials, API keys, browser profiles,
logs, virtual environments, screenshots, and the vendor tunnel binary.

## Documentation and acknowledgments

- [Local client setup and acceptance checks](docs/clients.md)
- [Optional ChatGPT tunnel setup](docs/chatgpt.md)
- [Optional macOS background service](docs/background-service.md)
- [FastMCP tools](https://gofastmcp.com/servers/tools)
- [Apple Music API](https://developer.apple.com/documentation/applemusicapi)
- [MusicKit authentication](https://developer.apple.com/documentation/applemusicapi/user-authentication-for-musickit)

The web API's endpoint behavior was checked against
[epheterson/applemusic-mcp](https://github.com/epheterson/applemusic-mcp/blob/main/src/applemusic_mcp/amp_api.py).
Browser sign-in uses the token mechanism from its
[browser authentication implementation](https://github.com/epheterson/applemusic-mcp/blob/main/src/applemusic_mcp/browser.py).
