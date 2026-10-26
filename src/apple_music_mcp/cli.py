"""Command-line entry point; default mode is an MCP stdio server."""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from collections.abc import Callable

import httpx

from .api import MusicAPI
from .auth import Credentials, MusicError, login_server
from .capabilities import capabilities
from .clients import add_commands, list_clients, show_config
from .doctor import add_doctor_command, doctor
from .install import add_install_command, install_client
from .native import NativeMusic
from .signin import SignInManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apple Music library and playlist MCP server")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="Run the FastMCP server over stdio")
    login_parser = commands.add_parser("login", help="Sign in directly on Apple's music website")
    login_parser.add_argument(
        "--web", action="store_true", help="Use web sign-in even with a developer token"
    )
    login_parser.add_argument(
        "--no-browser", action="store_true", help="Print the URL without opening it"
    )
    login_parser.add_argument(
        "--timeout", type=int, default=600, help="Sign-in time limit in seconds"
    )
    status_parser = commands.add_parser(
        "status", help="Check authentication without exposing credentials"
    )
    status_parser.add_argument(
        "--native", action="store_true", help="Also check Music.app automation access"
    )
    commands.add_parser("logout", help="Remove this server's locally stored music access token")
    add_commands(commands)
    add_install_command(commands)
    add_doctor_command(commands)
    return parser


def serve(_args) -> None:
    from .server import create_server

    create_server().run(transport="stdio", show_banner=False)


def web_login(credentials: Credentials, args) -> None:
    if args.no_browser:
        raise MusicError("Web sign-in requires a browser window; omit --no-browser.")
    from .browser_login import browser_login

    store = browser_login(credentials, timeout=args.timeout)
    print("Apple Music connected and library access verified. Storefront: " + store)


def musickit_login(credentials: Credentials, token: str, args) -> None:
    server, url = login_server(credentials, token)
    print("Open this local sign-in page:\n" + url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    deadline = time.monotonic() + max(1, min(args.timeout, 3600))
    try:
        while not server.authorized and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not server.authorized:
        raise MusicError("Sign-in timed out. Run login again when you are ready.")
    print("Apple Music connected. Storefront: " + server.storefront)


def login(args) -> None:
    credentials = Credentials()
    if credentials.user_token_from_environment():
        raise MusicError(
            "Remove APPLE_MUSIC_USER_TOKEN from the environment before signing in again."
        )
    manager = SignInManager(credentials)
    with manager.session():
        with httpx.Client(timeout=20) as client:
            token, web = credentials.developer_token(client, force_web=args.web)
        if web:
            web_login(credentials, args)
        else:
            musickit_login(credentials, token, args)


def status(args) -> None:
    api = MusicAPI()
    result = {
        "web_signed_in": bool(api.credentials.user_token()),
        "web_accessible": False,
        **capabilities(),
    }
    result.update(api.check_access() if result["web_signed_in"] else {})
    result.update({"native": NativeMusic().check_access()} if args.native else {})
    print(json.dumps(result, indent=2))
    if not result["web_accessible"] and not result.get("native", {}).get("accessible"):
        sys.exit(1)


def logout(_args) -> None:
    credentials = Credentials()
    (credentials.root / "credentials.json").unlink(missing_ok=True)
    credentials.forget_web_token()
    print("Removed this server's saved music token.")


COMMANDS: dict[str | None, Callable] = {
    None: serve,
    "serve": serve,
    "login": login,
    "status": status,
    "logout": logout,
    "clients": list_clients,
    "config": show_config,
    "install": install_client,
    "doctor": doctor,
}


def main() -> None:
    if sys.platform == "win32":
        # MCP and generated configuration are UTF-8, including redirected output.
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    try:
        COMMANDS[args.command](args)
    except MusicError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
