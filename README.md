# Apple Music MCP Server

![Platform: macOS](https://img.shields.io/badge/platform-macOS-black)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)
![Built with FastMCP 3](https://img.shields.io/badge/built_with-FastMCP_3-6E56CF)
![Transport: stdio](https://img.shields.io/badge/transport-stdio-00897B)

**Manage your Apple Music library and playlists from your AI coding agent.**

Search for music, add or remove songs, create playlists, and organize your library
through 17 MCP tools built with Python and FastMCP. Install the server on your own
Mac, sign in to your own Apple Music account, and connect your preferred client.

> Find the album version of “Get Lucky” by Daft Punk and add it to my library.

> Create a playlist called Evening with these songs, skipping duplicates.

> Remove this song from Evening, but keep it in my library.

The server runs directly on macOS. **No Docker, Linux, or hosted server is required.**
Your client starts the local MCP process when it connects; after setup, you do not
need a separate Terminal window running the server.

[Quick start](#quick-start) · [Client installation](#client-installation) ·
[Tools](#tools) · [Configuration](#configuration) ·
[Troubleshooting](#troubleshooting) · [Development](#development)

## Features

- **Catalog search:** find songs, albums, artists, and playlists.
- **Library management:** browse your songs, inspect details, and add or remove songs.
- **Playlist management:** create, rename, describe, delete, duplicate, and edit tracks.
- **Native Music.app tools:** reorder playlists and import local audio files.
- **Shared local sign-in:** configured clients use the same credential directory.
- **Client setup helpers:** generate settings or install them with backups and conflict checks.
- **Diagnostics:** check dependencies and discover tools before opening a client.

This is an independent integration. The default browser sign-in does not need an
Apple developer account. It uses Apple's web player and some undocumented endpoints,
which may change when Apple updates its player.

## Requirements

| Requirement | Details |
| --- | --- |
| macOS | The primary installation target; Music.app automation requires a Mac |
| Python 3.11+ | Check with `python3 --version`; use a newer interpreter if needed |
| Git | Required for the clone-based installation below |
| Apple Music account | An active subscription is required for personal library operations |
| Browser | Google Chrome, or Playwright Chromium installed below |
| MCP client | Install your coding agent or desktop client separately |
| Internet access | Required for Apple sign-in and online catalog/library operations |

Sign in to Music.app too if you want native playlist reordering or local audio
imports. Other operating systems are outside the primary setup documented here;
see [compatibility boundaries](docs/clients.md#compatibility-boundaries).

## Quick start

### 1. Clone and install

Run these commands in Terminal. `python3` must be Python 3.11 or newer.

```bash
git clone https://github.com/TomerBenShimol/apple-music-mcp-server.git
cd apple-music-mcp-server
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[browser]'
```

The sign-in helper uses Google Chrome when installed. If you do not have Chrome,
install its alternative browser:

```bash
.venv/bin/python -m playwright install chromium
```

All commands below run from this checkout. No virtual environment activation or
global package installation is required. Keep the checkout and `.venv` in place:
the client configurations point to their absolute paths.

### 2. Sign in to Apple Music

```bash
.venv/bin/apple-music-mcp login --web
.venv/bin/apple-music-mcp status
```

Complete Apple's sign-in and verification in the browser window. The helper checks
library access before saving the music token. A successful status check reports
`"web_accessible": true`.

Apple passwords and verification codes stay in Apple's sign-in flow. The temporary
browser profile is deleted when sign-in ends. Saved credentials stay on your Mac
in `~/.config/apple-music-mcp/credentials.json`, with private file permissions.

### 3. Connect your client

Quit the target client before changing its settings, then run **one** installer:

```bash
# Choose your client:
.venv/bin/apple-music-mcp install claude-code
# .venv/bin/apple-music-mcp install claude-desktop
# .venv/bin/apple-music-mcp install codex
# .venv/bin/apple-music-mcp install gemini-cli
# .venv/bin/apple-music-mcp install cursor
# .venv/bin/apple-music-mcp install vscode
```

Reopen the client, reload its MCP connections if needed, and approve the Apple Music
server when prompted. Your agent can then discover and call its tools.
See [client installation](#client-installation) for individual commands and paths.

### 4. Verify and try it

```bash
.venv/bin/apple-music-mcp doctor --probe
```

A successful probe reports `"status": "ready"` and `"tool_count": 17` under
`mcp_probe`. This checks the local server; `status` separately checks your account
with Apple.

Ask your agent:

> Check my Apple Music connection and find songs by Daft Punk.

Then request a library or playlist edit. You can ask naturally without naming the
MCP server or its individual tools. If sign-in is needed later, the agent can call
`connect_apple_music` to open the browser and check progress with `get_status`.
Keep the client running until sign-in finishes.

## Client installation

These commands register the installed server with an existing client. They default
to **user scope**, preserve unrelated settings, and create a private sibling backup
before updating an existing file. Installing an identical entry again makes no
change. A conflicting `apple-music` entry is rejected for you to resolve.

| Client | Installer target | Default macOS user configuration |
| --- | --- | --- |
| [Claude Code](#claude-code) | `claude-code` | `~/.claude.json` |
| [Claude Desktop](#claude-desktop) | `claude-desktop` | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| [Codex](#codex) | `codex` | `~/.codex/config.toml`, or `$CODEX_HOME/config.toml` |
| [Gemini CLI](#gemini-cli) | `gemini-cli` | `~/.gemini/settings.json` |
| [Cursor](#cursor) | `cursor` | `~/.cursor/mcp.json` |
| [VS Code](#vs-code) | `vscode` | `~/Library/Application Support/Code/User/mcp.json` |

The generators and installers are tested against these configuration formats.
End-to-end testing inside every client application is still outstanding. The
installer does not install the AI client or grant tool approvals.

### Claude Code

```bash
.venv/bin/apple-music-mcp install claude-code
```

Restart Claude Code and approve the server when prompted. For project scope:

```bash
.venv/bin/apple-music-mcp install claude-code --scope project --project-dir /absolute/path/to/project
```

Project scope writes `.mcp.json` in the selected project.

### Claude Desktop

```bash
.venv/bin/apple-music-mcp install claude-desktop
```

Quit and reopen Claude Desktop so it loads the updated settings. This installer
uses its local MCP configuration; it does not create a desktop extension bundle.

### Codex

```bash
.venv/bin/apple-music-mcp install codex
```

Restart Codex so it loads the TOML entry. The installer honors `CODEX_HOME` if set.
For project scope, add `--scope project --project-dir /absolute/path/to/project`;
the destination is `.codex/config.toml` in that project.

### Gemini CLI

```bash
.venv/bin/apple-music-mcp install gemini-cli
```

Restart Gemini CLI and approve the connection when prompted. For project scope,
add `--scope project --project-dir /absolute/path/to/project`; the destination is
`.gemini/settings.json` in that project.

### Cursor

```bash
.venv/bin/apple-music-mcp install cursor
```

Restart Cursor or reload its MCP connections and enable the server if requested.
For project scope, add `--scope project --project-dir /absolute/path/to/project`;
the destination is `.cursor/mcp.json` in that project.

### VS Code

```bash
.venv/bin/apple-music-mcp install vscode
```

Reload VS Code and approve/start the MCP server when prompted. For workspace scope:

```bash
.venv/bin/apple-music-mcp install vscode --scope project --project-dir /absolute/path/to/project
```

This writes `.vscode/mcp.json`. For an alternate editor profile or installation,
use `--config-file /absolute/path/to/mcp.json` to select the correct destination.

### Preview or configure manually

Preview an installation without writing settings:

```bash
.venv/bin/apple-music-mcp install claude-code --dry-run
```

Print configuration to merge yourself; replace `claude-code` with any target above:

```bash
.venv/bin/apple-music-mcp config claude-code
.venv/bin/apple-music-mcp clients
```

Codex output is TOML; other targets output JSON. The generated entry uses your
absolute virtual environment Python path and credential directory. Tokens are not
copied into client settings.

The installer leaves unsupported JSON comments, trailing commas, duplicate keys,
symbolic-link settings, and TOML structures it cannot extend safely untouched.
Use `config` and merge the output manually in those cases. See the
[full client setup guide](docs/clients.md) for overrides and acceptance checks.

### Other MCP clients

Generate a generic stdio configuration:

```bash
.venv/bin/apple-music-mcp config generic
```

The result has this shape; the command fills in your actual paths:

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

Adapt the root structure to the client's documented format. The server exposes
local stdio; a cloud application needs a connection that can reach your Mac.

### ChatGPT

The existing ChatGPT connection uses OpenAI's private Secure MCP Tunnel. It has a
separate setup and requires an active tunnel process on your Mac. Follow the
[ChatGPT connection guide](docs/chatgpt.md), with optional
[macOS background startup](docs/background-service.md).

The local installers above do not configure ChatGPT. Hosted HTTP deployment and
one-click plugin packages are not included in this installation flow.

## Tools

| Tool | Purpose |
| --- | --- |
| `get_status` | Check account sign-in and optional native automation access |
| `connect_apple_music` | Start human-completed sign-in in a local browser |
| `search_music` | Search catalog songs, albums, artists, or playlists |
| `search_library` | Search or browse your library songs |
| `get_song_details` | Look up one exact catalog or library song |
| `add_songs_to_library` | Add catalog songs to your library |
| `remove_songs_from_library` | Remove exact library songs |
| `list_playlists` | List your playlists and their IDs |
| `get_playlist_tracks` | Read ordered playlist membership |
| `create_playlist` | Create a playlist |
| `update_playlist` | Rename a playlist or change its description |
| `delete_playlist` | Delete an editable playlist |
| `add_songs_to_playlist` | Append songs, skipping duplicates by default |
| `remove_songs_from_playlist` | Remove playlist membership, keeping library songs |
| `duplicate_playlist` | Copy ordered contents into a new playlist |
| `reorder_playlist` | Reorder a native Music.app playlist with a recovery copy |
| `import_audio_files` | Import local audio files into Music.app |

### Music.app access

Native playlist reordering and local audio imports require Music.app. To check
access:

```bash
.venv/bin/apple-music-mcp status --native
```

Allow the calling application to control Music when macOS requests it. Permissions
are managed under **System Settings → Privacy & Security → Automation**. The agent
can also check through `get_status(check_native=true)`; permission for Terminal may
not cover the client application running your server.

The automatic backend uses web access when signed in, otherwise native access.
`search_library`, `list_playlists`, and `create_playlist` accept `backend="native"`
when needed. Catalog searches always use Apple's online catalog.

### IDs, pagination, and edits

- **Catalog songs:** numeric IDs from `search_music`; use these for library additions.
- **Web library songs and playlist memberships:** `i.…` IDs from the matching read tool.
- **Web library playlists:** `p.…` IDs.
- **Native Music.app objects:** 16-character hexadecimal persistent IDs.

Use IDs returned by the matching backend. Library removals need IDs from
`search_library`; playlist removals need membership IDs from `get_playlist_tracks`.
A playlist removal deletes every occurrence of the supplied membership ID.

Search/list responses include `next_offset` when another page exists; pass it back
as `offset`. Song additions and removals accept up to 100 IDs per call. Reordering
accepts the complete playlist order up to 20,000 IDs, including duplicates; audio
imports accept up to 25 file paths. Tools exposing `dry_run` can preview edits;
playlist creation and duplication do not expose it.

Removing a song from your **library** can also remove it from playlists and synced
devices. Removing it from a **playlist** keeps the library song. Adding songs to a
playlist does not explicitly add them to the library; Apple Music's own settings
may do so. Smart, special, and non-editable playlists are rejected for edits.

Web writes report `accepted` after Apple's success response; synchronization is
asynchronous. Native writes read back their result. Failed or timed-out writes are
not automatically retried. Partial failures include completed IDs: read the affected
resource before retrying. Native imports report unconfirmed files as `unconfirmed`.
Reordering preserves every existing occurrence and creates a recovery playlist;
that copy remains available if verification fails.

## Configuration

| Environment variable | Purpose |
| --- | --- |
| `APPLE_MUSIC_MCP_HOME` | Credential/settings directory; default `~/.config/apple-music-mcp` |
| `APPLE_MUSIC_STOREFRONT` | Catalog region before a signed-in storefront is available; default `us` |
| `APPLE_MUSIC_DEVELOPER_TOKEN` | Optional Apple Music developer token |
| `APPLE_MUSIC_USER_TOKEN` | Optional existing music token, overriding the saved token |

Personal operations detect the signed-in account's storefront. To select a catalog
region while installing a client:

```bash
.venv/bin/apple-music-mcp install cursor --storefront gb
```

Choose these options before the initial client install. If an existing entry has
different settings, resolve that entry or choose a different `--name`.

To use a different credential directory, use it for both sign-in and client setup:

```bash
APPLE_MUSIC_MCP_HOME="$HOME/.config/apple-music-work" .venv/bin/apple-music-mcp login --web
.venv/bin/apple-music-mcp install codex --name apple-music-work --data-dir "$HOME/.config/apple-music-work"
```

If upgrading from a different credential directory, use `--data-dir` with its
absolute path or sign in again. Moving the checkout or virtual environment requires
updating the client's stored Python path.

### Credentials and local processes

Tokens belong in your local credential store or environment, never in committed
client settings. Generated configurations contain paths and optional storefront
selection. Private settings backups may contain secrets from other integrations;
keep them private.

While `APPLE_MUSIC_USER_TOKEN` is set, `connect_apple_music` refuses a new sign-in
because the environment value would override it. `get_status` reports
`token_from_environment`.

On macOS, server processes share a local lock so music edits do not overlap and
concurrent clients reuse a sign-in flow. The native bridge passes JSON arguments
to a fixed JXA program instead of inserting user text into executable source.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Python installation fails | Check `python3 --version`; Python 3.11 or newer is required |
| Sign-in cannot open a browser | Install the `[browser]` extra and Chrome or Playwright Chromium |
| Tools do not appear in the client | Reopen/reload the client, approve the server, and check the selected profile or organization policy |
| Server cannot start | Run `doctor --probe`; verify the configured absolute Python path still exists |
| Account is disconnected | Run `status`, then `login --web`, or ask the agent to connect Apple Music |
| Music.app access is denied | Sign in to Music.app and check the calling app's Automation permission |
| Installer rejects an existing entry | Resolve that entry or choose another `--name`; use `config` for manual setup |
| Installer cannot parse settings | Comments/trailing commas or unsupported TOML may require a manual merge |
| An edit times out or partly succeeds | Read the affected library/playlist before retrying |

Useful diagnostics:

```bash
.venv/bin/apple-music-mcp doctor
.venv/bin/apple-music-mcp doctor --probe
.venv/bin/apple-music-mcp status
```

`doctor` checks local dependencies without reading tokens or contacting Apple.
`doctor --probe` also starts a temporary MCP process and discovers its tools; it
does not call music tools or change your library. `status` verifies your saved
account access with Apple. Browser executables and Automation permissions need
their own checks; `doctor` reports them as unchecked.

For an issue report, include your macOS/Python/client versions, the failing command,
and the error text. Review diagnostics and logs for private paths or account data
before sharing. Never include tokens or `credentials.json`.

## Updating and removing

To update an existing checkout, stop its client connections first, then run:

```bash
git pull --ff-only
.venv/bin/python -m pip install -e '.[browser]'
.venv/bin/apple-music-mcp doctor --probe
```

Reopen your clients afterward. Unchanged Python/credential paths do not require
reinstallation of their settings.

To disconnect a client, remove its `apple-music` entry from the configuration shown
above and reload the client. Once all clients are disconnected, you can delete the
checkout and virtual environment. To remove this server's saved music token first:

```bash
.venv/bin/apple-music-mcp logout
```

`logout` removes local saved tokens; it does not change an environment-supplied token
or promise to revoke account authorization at Apple. ChatGPT background service
removal has [separate instructions](docs/background-service.md).

## Development

```bash
.venv/bin/python -m pip install -e '.[dev,browser]'
.venv/bin/pytest -q
.venv/bin/ruff check src scripts tests
.venv/bin/ruff format --check src scripts tests
```

The automated suite checks tool schemas, IDs, protected playlists, dry runs,
pagination, duplicate detection, partial failures, timeouts, credential handling,
sign-in, process locking, client settings, and background startup. Tests do not
modify a real music library; some bind temporary localhost ports. Client format
tests and a successful MCP probe do not replace testing inside each client app.

`requirements.lock` and `requirements-browser.lock` capture the original tested
Python environment. To reproduce it, install the appropriate lock file followed by
this package with `--no-deps -e .`.

```text
src/apple_music_mcp/    FastMCP tools, web API, native bridge, sign-in, and client setup
scripts/               Optional ChatGPT tunnel and macOS service helpers
tests/                 Automated tests
docs/                  Client setup, ChatGPT connection, and background service guides
```

Credentials, API keys, browser profiles, logs, virtual environments, screenshots,
and the vendor tunnel binary are excluded from version control.

## Documentation and acknowledgments

- [Local client setup and acceptance checks](docs/clients.md)
- [Optional ChatGPT tunnel setup](docs/chatgpt.md)
- [Optional macOS background service](docs/background-service.md)
- [FastMCP tools](https://gofastmcp.com/servers/tools)
- [Apple Music API](https://developer.apple.com/documentation/applemusicapi)
- [MusicKit authentication](https://developer.apple.com/documentation/applemusicapi/user-authentication-for-musickit)

The web-player endpoint behavior was checked against
[epheterson/applemusic-mcp](https://github.com/epheterson/applemusic-mcp/blob/main/src/applemusic_mcp/amp_api.py).
Direct web sign-in follows the token mechanism in its
[browser authentication implementation](https://github.com/epheterson/applemusic-mcp/blob/main/src/applemusic_mcp/browser.py).
