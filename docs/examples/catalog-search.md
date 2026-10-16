# A catalog search through the MCP server

[Back to the README](../../README.md)

This is a real search run through the current MCP server on 2026-10-16, using
the US catalog. It used an empty temporary credential store and made no library
or playlist changes. Results and ordering can change.

A request like "Find Get Lucky by Daft Punk and show me the different versions"
can use this tool call:

```json
{
  "name": "search_music",
  "arguments": {
    "query": "Daft Punk Get Lucky",
    "kind": "songs",
    "limit": 3,
    "offset": 0
  }
}
```

The server returned these songs:

| Song | Artist | Album | Catalog ID |
| --- | --- | --- | --- |
| [Get Lucky](https://music.apple.com/us/album/get-lucky/617154241?i=617154366) | Daft Punk, Pharrell Williams & Nile Rodgers | Random Access Memories | `617154366` |
| [Get Lucky (Radio Edit)](https://music.apple.com/us/album/get-lucky-radio-edit/1459540243?i=1459540658) | Daft Punk, Pharrell Williams & Nile Rodgers | 2010s Hits | `1459540658` |
| [Get Lucky (feat. Pharrell Williams & Nile Rodgers) [Daft Punk Remix]](https://music.apple.com/us/album/get-lucky-feat-pharrell-williams-nile-rodgers-daft/664332737?i=664332744) | Daft Punk | Get Lucky (feat. Pharrell Williams & Nile Rodgers) [Daft Punk Remix] | `664332744` |

The first result is from Random Access Memories. The other results are a radio
edit and a remix, each with its own catalog ID. An agent can use those details
to check the version you meant before adding it to your library.

This example verifies catalog search only. Adding songs to a personal library
requires Apple Music sign-in and an active subscription.
