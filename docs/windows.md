# Windows setup

Run the server on your Windows PC and connect it to a local MCP client. You need
Windows 11, Python 3.11 or newer, Git, and an Apple Music subscription for personal
library access. You don't need a Mac, an Apple developer account, or the Windows
Apple Music app. Use native Windows Python for this setup; WSL is a different
runtime with its own paths and browser requirements.

## Install in PowerShell

Open PowerShell in the folder where you want to keep the project. Check that
`py -3 --version` reports Python 3.11 or newer. If the Python launcher is missing,
use `python` in place of `py -3` after checking `python --version`.

```powershell
git clone https://github.com/TomerBenShimol/apple-music-mcp-server.git
Set-Location apple-music-mcp-server
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[browser]"
.\.venv\Scripts\python.exe -m playwright install chromium
```

The Windows sign-in helper uses Playwright's Chromium, even if Chrome is already
installed. Keep this repository and its virtual environment at the same paths
once you have configured your clients.

These commands call the environment's Python directly. They work without running
`Activate.ps1` or changing PowerShell's execution policy.

## Sign in

```powershell
.\.venv\Scripts\python.exe -m apple_music_mcp login --web
.\.venv\Scripts\python.exe -m apple_music_mcp status
```

Complete Apple's sign-in in the browser that opens. Enter passwords and verification
codes there. The helper verifies library access before saving the music token and
deletes its temporary browser profile when it finishes. Status should report
`"web_accessible": true`.

Credentials default to `$env:USERPROFILE\.config\apple-music-mcp\credentials.json`.
They are stored as UTF-8 JSON under your Windows user profile and inherit the
folder's Windows access permissions. They are not encrypted by this project.
Keep this folder out of shared or synced directories and do not commit it.

For another credential directory, set it before sign-in and use the same directory
when installing the client:

```powershell
$env:APPLE_MUSIC_MCP_HOME = "$env:LOCALAPPDATA\apple-music-mcp"
.\.venv\Scripts\python.exe -m apple_music_mcp login --web
.\.venv\Scripts\python.exe -m apple_music_mcp install cursor --data-dir "$env:APPLE_MUSIC_MCP_HOME"
```

The generated client configuration saves the directory path, without copying tokens.

## Connect your client

Quit your client, then choose its installer target:

```powershell
.\.venv\Scripts\python.exe -m apple_music_mcp install claude-code
# .\.venv\Scripts\python.exe -m apple_music_mcp install claude-desktop
# .\.venv\Scripts\python.exe -m apple_music_mcp install codex
# .\.venv\Scripts\python.exe -m apple_music_mcp install gemini-cli
# .\.venv\Scripts\python.exe -m apple_music_mcp install cursor
# .\.venv\Scripts\python.exe -m apple_music_mcp install vscode
```

Reopen the client and approve the server. The client starts the server when it
connects, so a separate PowerShell window need not stay open. The installer uses
absolute executable paths and handles spaces and Unicode in folder names.

| Client | Default Windows user configuration |
| --- | --- |
| Claude Code | `%USERPROFILE%\.claude.json` |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` |
| Codex | `%USERPROFILE%\.codex\config.toml`, or `%CODEX_HOME%\config.toml` |
| Gemini CLI | `%USERPROFILE%\.gemini\settings.json` |
| Cursor | `%USERPROFILE%\.cursor\mcp.json` |
| VS Code | `%APPDATA%\Code\User\mcp.json` |

Use `--dry-run` to preview installation or `config <client>` to copy the settings
manually. Existing settings are backed up before changes. Alternate editor profiles
can use `--config-file`. Project configuration and conflict handling are covered
in the [client guide](clients.md).

## Verify the connection

```powershell
.\.venv\Scripts\python.exe -m apple_music_mcp doctor --probe
```

Look for `"status": "ready"`, `"tool_count": 15`, and
`"native_backend_available": false`. This checks local tool discovery without
contacting Apple. Use `status` separately to check account access. Then ask your
agent to search the catalog before requesting a library edit.

The server exposes search, song details, library additions and removals, and
playlist creation, renaming, copying, deletion, and track additions/removals.
Windows always uses web access for automatic backend selection. If you are signed
out, library tools ask you to sign in instead of trying Music.app automation.
Your agent can also open sign-in using `connect_apple_music`.

Playlist reordering and importing local audio require macOS Music.app automation.
Those two tools are absent from Windows discovery. Installing Apple's Windows app
does not enable them. The optional ChatGPT tunnel and macOS background-service
helpers have separate setup and are not Windows installers.

Sign-in and music edits use Windows process locks, allowing several local clients
to share one credential directory. Keep that directory on a local filesystem.
A process stopping releases its lock; the lock files themselves can stay on disk.

## Updating and removing

Close client connections before updating:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e ".[browser]"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m apple_music_mcp doctor --probe
```

To disconnect, remove the `apple-music` entry from the client's settings and reload
it. To delete the server's saved token:

```powershell
.\.venv\Scripts\python.exe -m apple_music_mcp logout
```

`logout` deletes the local credential; it does not guarantee Apple revokes access.
If you move the repository, update the executable path in each client configuration.

## Testing and troubleshooting

A missing browser error usually means Chromium was installed using a different
Python environment or Windows user. Repeat the browser installation command above.
If `py` selects an older Python, install a supported version and recreate `.venv`.
If a client cannot find the tools, check the interpreter path, reload its MCP
connections, and inspect its approval settings.

The automated suite covers Windows tool selection, web routing, Unicode paths,
configuration formats, and process locking. The CI workflow runs the suite on
Windows as well as macOS. Adding the workflow does not establish a passing run;
Windows browser sign-in and acceptance inside each client still need a real
Windows machine and account.

To run tests locally, install Node.js for the native bridge's mocked JavaScript
checks, then run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,browser]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src scripts tests
```
