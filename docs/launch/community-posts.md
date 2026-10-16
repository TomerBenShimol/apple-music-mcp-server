# Community post drafts

[Launch notes](README.md) · [Directory submissions](directories.md)

The drafts below are written for the maintainer to post under their own account.
They haven't been submitted. Review them before publishing and add a real demo
when one is available.

## Reddit: r/mcp

Use the showcase tag. The [community rules](https://www.reddit.com/r/mcp/about/rules.json)
allow self-promotion with disclosure, require the showcase tag for your own work,
and prohibit promotional AI slop. Edit this draft in your own voice before posting.

Title:

```text
I built a local Apple Music MCP server for library and playlist edits on a Mac
```

Body:

I built an Apple Music MCP server and would like feedback from people who use
Apple Music with their AI client.

It runs on your Mac using Python and FastMCP. You sign in with Apple in a browser,
and the client can then search the catalog, add or remove library songs, and edit
playlists. There are 17 tools, including Music.app tools for reordering playlists
and importing local audio.

For example, you can ask it to find a particular version of a song and add it to
your library, or copy a playlist and change its contents. Your saved music token
stays on your Mac. The default browser sign-in doesn't need an Apple developer
account, and you don't need Docker or a hosted server.

Setup commands are included for Claude Code, Claude Desktop, Codex, Gemini CLI,
Cursor, and VS Code. The configuration formats have automated tests. Testing
inside every client app is still pending, so I'd especially like to hear where
the setup instructions work or get stuck.

Intel Macs need extra build tools for a dependency; the README links to those steps.

One limitation: browser sign-in uses Apple's web player and some undocumented
endpoints, so Apple changes can break it. Native reordering and audio imports
also need Music.app permissions. ChatGPT has a separate tunnel setup.

Code and installation:
https://github.com/TomerBenShimol/apple-music-mcp-server

There's also a [real catalog search example](https://github.com/TomerBenShimol/apple-music-mcp-server/blob/main/docs/examples/catalog-search.md)
showing the album version, radio edit, and remix returned for Get Lucky.

If you try it, which client did you use, and was there anything unclear in setup?

## Hacker News: Show HN

Use this once someone can follow a fresh installation and try the project. The
[Show HN guidelines](https://news.ycombinator.com/showhn.html) call for a working
project, a title starting with Show HN, and a maker who can discuss the work.
They also prohibit asking friends to coordinate votes or comments.

Title:

```text
Show HN: A local Apple Music MCP server for library and playlist management
```

URL:

```text
https://github.com/TomerBenShimol/apple-music-mcp-server
```

First comment:

I built a local MCP server for managing Apple Music through an AI client. It has
17 tools for catalog searches, library additions and removals, and playlist edits.
Music.app handles playlist reordering and local audio imports.

It's Python with FastMCP over stdio. The client starts the server, and you complete
Apple sign-in in a browser. Saved music credentials stay on the Mac. The default
sign-in works without an Apple developer account.

The repo has configuration generators and installers for six local clients,
including Claude Code, Codex, and Cursor. They back up existing settings and stop
on conflicting entries. Those formats are tested; testing inside every client
application is still pending.

The web backend relies on Apple's web player and undocumented endpoints, which
makes it sensitive to Apple changes. Web edits report that Apple accepted the
request, with syncing happening afterward. Failed edits aren't automatically
retried. Native operations read back the result, and playlist reordering keeps a
recovery copy.

Intel installation needs extra build tools for a dependency. The README links to
the build instructions.

I'd appreciate feedback on setup and on how clearly the tools distinguish removing
a library song from removing it from a playlist.

## Short post for a personal feed

Use on an account where you normally share your projects. Check the destination's
rules before posting.

I built a local Apple Music MCP server for Mac. It lets your AI client search for
songs, manage your library, and edit playlists. Python + FastMCP, with 17 tools
and setup commands for six clients. Sign in with Apple in a browser; the default
setup doesn't need an Apple developer account.

Code and setup: https://github.com/TomerBenShimol/apple-music-mcp-server

I'd like feedback on the installation instructions, especially from people trying
it with different clients.
