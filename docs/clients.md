# Local MCP client setup

Install this project with its browser extra, then run commands using that Python
environment. Every client starts the same `python -m apple_music_mcp serve` command.
These are local stdio integrations; hosting and remote HTTP setup are separate work.

## Generate configuration

```bash
apple-music-mcp clients
apple-music-mcp config claude-code
apple-music-mcp config claude-desktop
apple-music-mcp config codex
apple-music-mcp config gemini-cli
apple-music-mcp config cursor
apple-music-mcp config vscode
apple-music-mcp config generic
```

Use the executable in your virtual environment if it is not on PATH. The generated
Python path preserves virtual environments, including paths containing spaces. Use
`--python /absolute/path/to/python` to select another existing interpreter with this
package installed. Do not delete that environment while clients depend on it.

All configurations point to one credential directory. For an existing sign-in, pass
`--data-dir /absolute/path/to/existing/settings`. Tokens are never copied into client
configuration. An optional `--storefront gb` selects the unauthenticated catalog region;
personal operations detect the signed-in account's storefront.

Use `--name apple-music` to customize the server entry. Names use lowercase letters,
digits, and hyphens to avoid client namespace ambiguities. Generated configurations
do not disable tool confirmations or mark the server universally trusted.

## Install into a client

```bash
apple-music-mcp install claude-code --dry-run
apple-music-mcp install claude-code
apple-music-mcp install codex
apple-music-mcp install gemini-cli
apple-music-mcp install claude-desktop
apple-music-mcp install cursor
apple-music-mcp install vscode --scope project
```

Installation defaults to user scope. `--scope project --project-dir /path/to/project`
selects project settings for clients that support them. `--config-file /path/to/settings`
overrides the destination, including alternate editor profiles and generic clients.
`CODEX_HOME` is honored for Codex user settings. Quit the client before editing its
configuration so it does not overwrite your changes on exit.

The installer preserves unrelated settings and creates a private sibling backup
before replacing an existing file. It prints the backup path without printing
existing settings. Repeating the same install makes no change. A conflicting server
name is rejected; edit/remove that entry in the client or choose another `--name`.
It does not install the AI client itself or grant tool approvals.

JSON with comments, trailing commas, duplicate keys, and TOML structures that cannot
be safely extended are left untouched. For those files, use `config` and merge the
entry in your editor. Symbolic-link settings require an explicit real file path.
Keep backups private: they may contain credentials belonging to other integrations.

## Configuration formats

Merge the generated entry into existing configuration instead of replacing the
entire file. Keep unrelated settings and MCP servers.

| Client | Format / root | Common configuration location |
| --- | --- | --- |
| Claude Code | JSON / `mcpServers` | User `~/.claude.json`; project `.mcp.json` |
| Claude Desktop | JSON / `mcpServers` | macOS `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows `%APPDATA%/Claude/claude_desktop_config.json` |
| Codex | TOML / `mcp_servers` | `~/.codex/config.toml`; project `.codex/config.toml` |
| Gemini CLI | JSON / `mcpServers` | `~/.gemini/settings.json`; project `.gemini/settings.json` |
| Cursor | JSON / `mcpServers` | `~/.cursor/mcp.json`; project `.cursor/mcp.json` |
| VS Code | JSON / `servers` | Project `.vscode/mcp.json`, or **MCP: Open User Configuration** |
| Generic | JSON / `mcpServers` | Follow your client's documentation |

Claude Code and VS Code entries explicitly declare `type: stdio`. Codex uses TOML,
not JSON. Paths are for the host running the client; remote development environments
need an installation and credentials on that host.

Reload MCP connections or restart the client after configuration. Approve the server
when the client requests it. Ask for account status or a catalog search first, then
complete Apple Music sign-in before library edits.

## Diagnose setup

```bash
apple-music-mcp doctor
apple-music-mcp doctor --probe
apple-music-mcp status
```

`doctor` checks this Python environment and reports dependency versions, optional
browser support, and native-backend availability. It does not read saved tokens or
contact Apple. Browser executables and macOS Automation permission are explicitly
reported as unchecked. If using `config --python`, run diagnostics through that
interpreter: `/path/to/python -m apple_music_mcp doctor --probe`.

`--probe` starts a temporary stdio server, initializes an MCP connection, and lists
tools. It does not call music tools, open a sign-in browser, or modify the library.
A successful probe verifies the server runtime, not integration inside every client.
Use `status` separately to verify the Apple Music account over the network.

For each client, complete these acceptance checks after installing:

1. Reload the client and confirm that Apple Music tools appear.
2. Ask for a catalog search and inspect the returned song IDs.
3. Check account status and complete sign-in if needed.
4. Preview a library addition with `dry_run=true` before an explicitly requested edit.
5. Restart the client and confirm the connection and saved sign-in still work.

If an entry cannot launch, check its absolute Python path and dependencies. If tools
do not appear, check client approvals, organization policies, or the selected profile.
If Apple Music needs sign-in, use `connect_apple_music` or `login --web`; MCP
configuration does not itself authorize an Apple Music account.

## Compatibility boundaries

The configuration generators are tested against their documented formats. Actual
end-to-end use in each provider's application is a separate acceptance check; a
generated entry does not prove that a particular installed client version loaded it.

Music.app automation, native playlist reordering, and local audio imports require
macOS. Windows uses the web backend and exposes 15 tools; the two native-only
tools are hidden. Edits and sign-in share process locks on both systems. Follow
the [Windows setup guide](windows.md) for PowerShell commands and browser installation.
Windows browser sign-in and use inside each client still require acceptance testing
on a Windows machine. The optional macOS service and ChatGPT tunnel helpers are
separate from the Windows stdio setup.

## References

- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Claude Desktop local servers](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
- [Codex MCP](https://developers.openai.com/codex/mcp)
- [Gemini CLI MCP](https://geminicli.com/docs/tools/mcp-server/)
- [Cursor MCP](https://cursor.com/docs/mcp)
- [VS Code MCP](https://code.visualstudio.com/docs/agent-customization/mcp-servers)

Configuration conventions reviewed on 2026-10-16.
