"""Command-line entry point; default mode is an MCP stdio server."""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser

import httpx

from .api import MusicAPI
from .auth import Credentials, MusicError, login_server
from .native import NativeMusic


def main() -> None:
    parser = argparse.ArgumentParser(description="Apple Music library and playlist MCP for Hermes")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="Run the FastMCP server over stdio")
    login = commands.add_parser("login", help="Sign in directly on Apple's music website")
    login.add_argument(
        "--web", action="store_true", help="Use web sign-in even with a developer token"
    )
    login.add_argument("--no-browser", action="store_true", help="Print the URL without opening it")
    login.add_argument("--timeout", type=int, default=600, help="Sign-in time limit in seconds")
    status = commands.add_parser("status", help="Check authentication without exposing credentials")
    status.add_argument(
        "--native", action="store_true", help="Also check Music.app automation access"
    )
    commands.add_parser("logout", help="Remove this server's locally stored music access token")
    args = parser.parse_args()
    try:
        if args.command in {None, "serve"}:
            from .server import create_server

            create_server().run(transport="stdio", show_banner=False)
        elif args.command == "login":
            credentials = Credentials()
            with httpx.Client(timeout=20) as client:
                token, web = credentials.developer_token(client, force_web=args.web)
            if web:
                if args.no_browser:
                    raise MusicError("Web sign-in requires a browser window; omit --no-browser.")
                from .browser_login import browser_login

                store = browser_login(credentials, timeout=args.timeout)
                print("Apple Music connected and library access verified. Storefront: " + store)
                return
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
            store = server.storefront
            print("Apple Music connected. Storefront: " + store)
        elif args.command == "status":
            api = MusicAPI()
            result = {"web_signed_in": bool(api.credentials.user_token()), "web_accessible": False}
            result.update(api.check_access() if result["web_signed_in"] else {})
            result.update({"native": NativeMusic().check_access()} if args.native else {})
            print(json.dumps(result, indent=2))
            if not result["web_accessible"] and not result.get("native", {}).get("accessible"):
                sys.exit(1)
        elif args.command == "logout":
            (Credentials().root / "credentials.json").unlink(missing_ok=True)
            print("Removed this server's saved music token.")
    except MusicError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
