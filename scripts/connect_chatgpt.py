"""Start OpenAI's private tunnel to the already installed Apple Music MCP.

Run from a terminal: the Platform runtime key is entered without echo and stays
only in the child process environment. No Apple or OpenAI secret is written here.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CLIENT = PROJECT / ".chatgpt" / "tunnel-client"
RUNTIME = Path.home() / ".local/share/tomer-apple-music-mcp"
PROFILE_DIR = Path.home() / ".config/tomer-apple-music-mcp/chatgpt-profiles"
PROFILE = "apple-music-chatgpt"
TUNNEL_ID = re.compile(r"tunnel_[A-Za-z0-9_-]+\Z")


class SetupError(Exception):
    """A setup problem the user can fix; its text is safe to print."""


def require_installed() -> None:
    if not sys.stdin.isatty():
        raise SetupError("Run this setup in Terminal so the API key can be entered privately.")
    if not CLIENT.is_file() or not (RUNTIME / ".venv/bin/python").is_file():
        raise SetupError(
            "The Apple Music MCP runtime and OpenAI tunnel-client must be installed first."
        )


def read_tunnel_id() -> str:
    tunnel_id = input("Tunnel ID (tunnel_…): ").strip()
    if not TUNNEL_ID.fullmatch(tunnel_id):
        raise SetupError("Enter the tunnel ID from Platform settings.")
    return tunnel_id


def read_api_key() -> str:
    api_key = getpass.getpass("OpenAI runtime API key (hidden; never saved): ").strip()
    if not api_key or any(c.isspace() for c in api_key):
        raise SetupError("The runtime API key is empty or invalid.")
    return api_key


def tunnel_environment(api_key):
    # This connection is specifically to OpenAI and our one MCP command. Ignore
    # inherited tunnel overrides that could change its endpoint, target, or logging.
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(
            (
                "CONTROL_PLANE_",
                "TUNNEL_CLIENT_",
                "MCP_",
                "HARPOON_",
                "HEALTH_",
                "ADMIN_UI_",
                "LOG_",
                "CLOUDFLARED_",
            )
        )
        and name not in {"ALLOW_REMOTE_UI", "OPEN_WEB_UI", "PID_FILE"}
    }
    environment["CONTROL_PLANE_API_KEY"] = api_key
    environment["APPLE_MUSIC_STOREFRONT"] = "il"
    return environment


def write_profile(tunnel_id):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    profile_file = PROFILE_DIR / (PROFILE + ".yaml")
    command = shlex.join([str(RUNTIME / ".venv/bin/python"), "-m", "apple_music_mcp", "serve"])
    settings = {
        "config_version": 1,
        "control_plane": {
            "base_url": "https://api.openai.com",
            "tunnel_id": tunnel_id,
            "api_key": "env:CONTROL_PLANE_API_KEY",
        },
        "health": {"listen_addr": "127.0.0.1:0"},
        "admin_ui": {"open_browser": False},
        "log": {"level": "info", "format": "json"},
        "mcp": {
            "commands": [{"channel": "main", "command": command}],
            "stdio_send_initialized_notification": True,
            "max_concurrent_requests": 1,
        },
    }
    # JSON is also YAML; no new configuration dependency is needed.
    temporary = profile_file.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(settings, stream, indent=2)
    temporary.replace(profile_file)


def common_arguments():
    common = [
        str(CLIENT),
        "--profile",
        PROFILE,
        "--profile-dir",
        str(PROFILE_DIR),
        "--mcp.stdio-send-initialized-notification",
        "--mcp.max-concurrent-requests",
        "1",
        "--health.listen-addr",
        "127.0.0.1:0",
        "--log.http-raw-unsafe=false",
        "--allow-remote-ui=false",
    ]
    return common


def main() -> int:
    try:
        require_installed()
        print("Create a private tunnel associated with your ChatGPT workspace at:")
        print("https://platform.openai.com/settings/organization/tunnels")
        print("Create a runtime API key with Tunnels Read + Use at:")
        print("https://platform.openai.com/settings/organization/api-keys")
        print("Only music tool calls and results pass through this tunnel to ChatGPT.")
        tunnel_id = read_tunnel_id()
        api_key = read_api_key()
    except SetupError as error:
        print(error)
        return 1
    write_profile(tunnel_id)
    environment = tunnel_environment(api_key)
    common = common_arguments()
    doctor = subprocess.run(
        [common[0], "doctor", *common[1:], "--explain"], env=environment, cwd=RUNTIME, check=False
    )
    if doctor.returncode:
        print("The tunnel check failed. Resolve the reported access/configuration issue first.")
        return doctor.returncode
    print("Keep this Terminal window open while using Apple Music in ChatGPT.")
    print("In ChatGPT Plugins: + → Add custom MCP server → Connection: Tunnel.")
    print("Select the tunnel above, name it 'My Apple Music', and select No authentication.")
    print("The private tunnel restricts access through your OpenAI account/workspace.")
    print("Review and approve the connection, then install the resulting personal plugin.")
    print("Apple Music sign-in must also be completed for personal library operations.")
    return subprocess.run(
        [common[0], "run", *common[1:]], env=environment, cwd=RUNTIME, check=False
    ).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. No API key was saved.")
        raise SystemExit(130) from None
