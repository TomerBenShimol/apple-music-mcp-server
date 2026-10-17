# Directory submission copy

[Launch notes](README.md) · [Community posts](community-posts.md)

These fields describe the current local server. They aren't confirmation that a
directory has accepted or listed it.

## Shared details

Name: Apple Music MCP Server

Repository: https://github.com/TomerBenShimol/apple-music-mcp-server

Short description:

> Search Apple Music and manage your library and playlists from your favorite AI
> client. Runs locally on your Mac with Python and FastMCP.

Longer description:

> A local Apple Music MCP server with 17 tools for catalog searches, library edits,
> and playlist management. It can also reorder playlists and import local audio
> through Music.app. Sign in with Apple in a browser; the default setup doesn't
> need an Apple developer account. Saved music credentials stay on your Mac.
>
> Includes configuration generators and installers for Claude Code, Claude Desktop,
> Codex, Gemini CLI, Cursor, and VS Code. The configuration formats have automated
> tests; testing inside every client app is still pending. ChatGPT uses a separate
> Secure MCP Tunnel setup.

Language: Python

Platform: macOS

Transport: stdio

License: [MIT](../../LICENSE)

Requirements: Python 3.11+, a browser, an MCP client, and an Apple Music account
with an active subscription for personal library operations. Native tools also
need Music.app access. See the project README for installation and sign-in.

The server runs on the user's Mac. It doesn't provide a public MCP URL.

## Glama

Follow [Glama's submission instructions](https://glama.ai/mcp/faq) and choose the
GitHub repository submission under [MCP servers](https://glama.ai/mcp/servers).
Use the shared name, URL, and description above. This is a local server listing;
the remote connector flow isn't the right submission type.

If the form asks for a license, select MIT. If it asks about a successful test or
supported client, report only what has been verified. Glama checks licensing,
security, and server health; a listing request doesn't establish a passing result.

## Awesome MCP Servers

Contribution guide:
https://github.com/punkpeye/awesome-mcp-servers/blob/main/CONTRIBUTING.md

Suggested section: Art & Culture, alongside the existing music integrations.
Keep the entry in alphabetical order by its repository label.

Proposed entry:

```markdown
- [TomerBenShimol/apple-music-mcp-server](https://github.com/TomerBenShimol/apple-music-mcp-server) 🐍 ☁️ 🏠 🍎 - Search Apple Music and manage library songs and playlists from a local Python MCP server.
```

The list's cloud marker means the server talks to a remote API; it doesn't mean
this project hosts the MCP process. The local marker covers Music.app automation.
The Python and macOS markers describe the implementation and primary target.

Pull request title:

```text
Add Apple Music MCP Server
```

Pull request body:

```markdown
Adds a Python Apple Music MCP server to Art & Culture.

It runs locally on macOS over stdio. Its 17 tools cover catalog search, library
additions and removals, playlist management, native playlist reordering, and local
audio imports. Browser sign-in works without an Apple developer account.

The repository includes setup commands for six local MCP clients. Configuration
formats are covered by automated tests; end-to-end testing in every client app
is still pending.

I maintain the project: https://github.com/TomerBenShimol/apple-music-mcp-server
```

Before opening a pull request, check that the project isn't already listed and
that another submission isn't open. Add only this entry and follow the current
maintainer instructions.

## Official MCP Registry

This is a later distribution step. The current installation starts with a Git
clone. The official registry can describe a published Python package, but that
requires a package release and registry metadata first. See the
[registry requirements](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/official-registry-requirements.md).

Don't submit an invented hosted URL or advertise a PyPI install command until
that package has actually been published and checked.
