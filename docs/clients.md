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

## Compatibility boundaries

The configuration generators are tested against their documented formats. Actual
end-to-end use in each provider's application is a separate acceptance check; a
generated entry does not prove that a particular installed client version loaded it.

Music.app automation, native playlist reordering, and local audio imports require
macOS. The web backend is intended for other operating systems, but Windows currently
lacks shared process locking for edits and sign-in. Treat Windows runtime support as
experimental and avoid simultaneous clients there until locking is implemented and
tested. Browser installation and permissions must be checked on each operating system.

## References

- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Claude Desktop local servers](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
- [Codex MCP](https://developers.openai.com/codex/mcp)
- [Gemini CLI MCP](https://geminicli.com/docs/tools/mcp-server/)
- [Cursor MCP](https://cursor.com/docs/mcp)
- [VS Code MCP](https://code.visualstudio.com/docs/agent-customization/mcp-servers)

Configuration conventions reviewed on 2026-10-16.
