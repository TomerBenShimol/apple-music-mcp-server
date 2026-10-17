# Sharing Apple Music MCP

[Project README](../../README.md) · [Directory submissions](directories.md) ·
[Community posts](community-posts.md)

Start with people who already use MCP and Apple Music. A working example of finding
songs and building a playlist will tell them more than a long feature announcement.
The [catalog search example](../examples/catalog-search.md) is from a real read-only
MCP call. A video of a full playlist edit still needs to be recorded.

## Before posting

- The repository uses the [MIT License](../../LICENSE).
- Try a fresh clone, sign-in, and connection in at least one target client. Record
  which client and version you actually used.
- Make a short recording of a real interaction. Use a new demo playlist and avoid
  showing your account details or tokens.
- Create a tagged release with setup instructions and the limitations below.

The repository has automated configuration tests for Claude Code, Claude Desktop,
Codex, Gemini CLI, Cursor, and VS Code. That doesn't establish that every installed
version of those applications has loaded it successfully. Keep that distinction in
posts until the client acceptance checks in [the setup guide](../clients.md) pass.

## Suggested order

1. Add the repository to Glama and submit a pull request to Awesome MCP Servers.
2. Share the project on r/mcp using its showcase tag. Include a demo when one is ready.
3. Submit to Show HN once a new user can follow the instructions and try it.
4. Use installation feedback to fix the next release before posting to more communities.

The [directory submission fields](directories.md) and
[post drafts](community-posts.md) are ready to adapt. They are drafts, not a record
of submissions. Copy only the post body when publishing and check the site's rules
again if time has passed.

## What to say

The useful details are concrete: 17 tools, a local Python server, browser sign-in,
and library and playlist edits. The default sign-in works without an Apple developer
account. Users keep their saved music token on their own Mac.

Be clear about the limits:

- macOS is the main target. Playlist reordering and audio imports need Music.app.
- Intel Macs need extra build tools for a dependency; point users to the
  [installation notes](../installation.md#intel-macs).
- Browser sign-in uses Apple's web player and some undocumented endpoints. Apple
  changes can break it.
- The six local installers don't configure ChatGPT. Its connection has a separate
  Secure MCP Tunnel setup.
- There is no hosted endpoint or one-click plugin package in the current install flow.
- The project doesn't offer music playback controls, listening-history analysis,
  or automatic recommendations.

Don't describe a planned feature as shipped, claim all clients have been tested,
or present a scripted example as a recording of a real tool call.

## A short demo to record

This is a recording plan, not a test result. The playlist creation step changes
Apple Music; run it only when you're ready to make that demo playlist.

1. Show the client connected and ask it to check Apple Music access.
2. Ask: "Find three Daft Punk songs for a playlist. Show me the song names first."
3. Check the matches, then ask: "Create a playlist called MCP Demo with those songs."
4. Open the playlist in Apple Music and show the result.

Keep the recording focused on the request and result. Don't include sign-in,
verification codes, credential files, or private library browsing. Any captions
should describe what the recording actually shows.

## Measure the response

Use GitHub's repository traffic view to compare views, unique visitors, clones,
and referring sites before and after each post. Note the submission URL and date
outside this public folder if you want to keep a private launch log.

Also count useful feedback: installation attempts, reproducible issues, and requests
from people using another client. Those tell us what needs work. Avoid promises
about traffic or stars and don't ask people to coordinate votes.

## Sources

- [Awesome MCP Servers contribution guide](https://github.com/punkpeye/awesome-mcp-servers/blob/main/CONTRIBUTING.md)
- [Glama submission instructions](https://glama.ai/mcp/faq)
- [r/mcp rules](https://www.reddit.com/r/mcp/about/rules.json)
- [Show HN guidelines](https://news.ycombinator.com/showhn.html)
- [GitHub repository traffic](https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-traffic-to-a-repository)

Submission rules checked on 2026-10-16.
