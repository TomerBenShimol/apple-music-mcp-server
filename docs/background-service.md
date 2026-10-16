# macOS background service

`scripts/chatgpt_service.py` runs the existing private tunnel under a user
LaunchAgent. It stores the OpenAI runtime key in macOS Keychain, starts at login,
and restarts after failures. It does not keep a Terminal window open.

## Prerequisites

- The package installed at `~/.local/share/apple-music-mcp/.venv`.
- A verified official tunnel client, originally placed at `.chatgpt/tunnel-client`.
- A tunnel profile created by `scripts/connect_chatgpt.py`:
  `~/.config/apple-music-mcp/chatgpt-profiles/apple-music-chatgpt.yaml`.
- Your existing tunnel runtime key. Enter it only in the local setup prompt.

This preparation copies the helper and vendor client outside Desktop/iCloud,
and creates the background profile **without saving the key**. Run it from the
repository root after creating the foreground profile:

```bash
.venv/bin/python - <<'PY'
import json
import shutil
from pathlib import Path

runtime = Path.home() / '.local/share/apple-music-mcp'
helper = runtime / 'chatgpt'
helper.mkdir(parents=True, exist_ok=True, mode=0o700)
helper.chmod(0o700)
for source, destination in [
    (Path('scripts/chatgpt_service.py'), helper / 'chatgpt_service.py'),
    (Path('.chatgpt/tunnel-client'), helper / 'tunnel-client'),
]:
    shutil.copyfile(source, destination)
    destination.chmod(0o700)
profiles = Path.home() / '.config/apple-music-mcp/chatgpt-profiles'
settings = json.loads((profiles / 'apple-music-chatgpt.yaml').read_text())
settings['health'] = {'listen_addr': '127.0.0.1:61356'}
profile = profiles / 'apple-music-background.yaml'
profile.touch(mode=0o600, exist_ok=True)
profile.chmod(0o600)
profile.write_text(json.dumps(settings, indent=2))
PY
~/.local/share/apple-music-mcp/.venv/bin/python \
  ~/.local/share/apple-music-mcp/chatgpt/chatgpt_service.py install
```

The installer asks for the key privately, saves and verifies it in Keychain,
loads the LaunchAgent, and waits for readiness. When it reports **Connected.
Automatic startup is enabled**, Terminal may close. Keep your Mac awake and online.

The helper recognizes the original deployment's foreground client under
`~/Desktop/apple-music-mcp/.chatgpt/` and stops it after successful startup.
If you launched the old client from a different path, close that foreground
connection after the background connection reports ready.

## Manage the service

Use the installed Python and helper paths above with these actions:

| Action | Result |
| --- | --- |
| `status` | Check the local readiness endpoint |
| `stop` | Unload the service for this login session |
| `start` | Load the saved service again |
| `install` | Save a replacement key and reinstall/restart the service |

To disable automatic startup permanently, stop the service and remove
`~/Library/LaunchAgents/local.apple-music-chatgpt.plist`.
This does not change Hermes or disconnect the ChatGPT plugin.

## Storage and boundaries

- LaunchAgent: `~/Library/LaunchAgents/local.apple-music-chatgpt.plist`.
- Keychain service: `Apple Music — OpenAI tunnel`; account: the tunnel ID.
- Operational logs: `~/.local/state/apple-music-mcp/` with private permissions.
- Health address: `127.0.0.1:61356` only.
- Runtime keys are not stored in source, command arguments, logs, or the plist.
- Raw HTTP logging and remote admin access are disabled.

Native Music.app operations may need macOS Automation permission for the process
running the installed server. Web operations use the saved Apple Music token.
