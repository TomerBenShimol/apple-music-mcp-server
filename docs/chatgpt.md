# Connect Apple Music MCP to ChatGPT

[Back to the README](../README.md) · [Local client setup](clients.md)

ChatGPT uses a cloud connection, while this project runs on your Mac. The six
local client installers do not configure ChatGPT; the existing integration uses
OpenAI's Secure MCP Tunnel to reach the local server. Your Mac must stay awake,
online, and running the tunnel for ChatGPT to reach it. Tunnel availability and
permissions depend on your OpenAI account and workspace.

Complete the [installation and Apple Music sign-in](../README.md#quick-start)
first. The additional setup below is optional for local coding agents.
Run the commands below from the root of your repository checkout.

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
[the background service setup](background-service.md). That service stores
its runtime key in macOS Keychain. Your Mac must remain awake and online.
