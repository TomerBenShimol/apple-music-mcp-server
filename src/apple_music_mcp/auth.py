"""Local credential storage and developer-token MusicKit authorization.

No password enters this process. MusicKit handles sign-in with Apple and returns
only the music authorization token to the temporary loopback server.
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx


class MusicError(Exception):
    """An actionable failure suitable for an MCP tool response."""


class TransientMusicError(MusicError):
    """A failure worth retrying later: the network, a rate limit, or an Apple server error."""


USER_TOKEN_ENV = "APPLE_MUSIC_USER_TOKEN"


def data_dir() -> Path:
    return Path(
        os.environ.get("APPLE_MUSIC_MCP_HOME", "~/.config/tomer-apple-music-mcp")
    ).expanduser()


def private_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".music-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, OSError) as exc:
        raise MusicError(f"Cannot read settings at {path}. Restore or remove that file.") from exc


def claims(token: str) -> dict:
    """Decode public JWT metadata for expiry; this does not verify authenticity."""
    try:
        segment = token.split(".")[1]
        value = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
    except (ValueError, IndexError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def checked_explicit(token: str) -> str:
    if claims(token).get("exp", 0) <= time.time():
        raise MusicError("APPLE_MUSIC_DEVELOPER_TOKEN is invalid or expired.")
    return token


def is_current_web_token(token: str) -> bool:
    payload = claims(token)
    return payload.get("iss") == "AMPWebPlay" and payload.get("exp", 0) > time.time() + 60


def scrape_web_token(client: httpx.Client) -> str:
    try:
        page = client.get("https://music.apple.com/us/new", follow_redirects=True)
        page.raise_for_status()
        bundles = re.findall(r"/assets/index~[A-Za-z0-9]+\.js", page.text)
        if not bundles:
            raise MusicError("Apple changed its web player. Use an Apple developer token.")
        script = client.get("https://music.apple.com" + bundles[0])
        script.raise_for_status()
    except httpx.HTTPError as exc:
        raise MusicError("Cannot reach Apple's web player to initialize catalog access.") from exc
    valid = [t for t in JWT.findall(script.text) if is_current_web_token(t)]
    if not valid:
        raise MusicError("No current Apple web-player token found. Try again later.")
    return valid[0]


class Credentials:
    def __init__(self, root: Path | None = None):
        self.root = root or data_dir()

    def user_token(self) -> str | None:
        return os.environ.get(USER_TOKEN_ENV) or read_json(self.root / "credentials.json").get(
            "user_token"
        )

    def user_token_from_environment(self) -> bool:
        return bool(os.environ.get(USER_TOKEN_ENV))

    @staticmethod
    def validate_user_token(token: str) -> None:
        if (
            not isinstance(token, str)
            or not 20 <= len(token) <= 16384
            or any(char.isspace() for char in token)
        ):
            raise MusicError("Apple returned an invalid music authorization token.")

    def save_user_token(self, token: str, source: str | None = None) -> None:
        self.validate_user_token(token)
        private_json(
            self.root / "credentials.json",
            {"user_token": token, "saved_at": time.time(), "source": source},
        )

    def user_token_source(self) -> str | None:
        if os.environ.get(USER_TOKEN_ENV):
            return None
        return read_json(self.root / "credentials.json").get("source")

    def forget_web_token(self) -> None:
        (self.root / "web-token.json").unlink(missing_ok=True)

    def developer_token(self, client: httpx.Client, force_web: bool = False) -> tuple[str, bool]:
        """Return (token, web_player). An explicit developer token takes precedence."""
        explicit = os.environ.get("APPLE_MUSIC_DEVELOPER_TOKEN")
        if explicit and not force_web:
            return checked_explicit(explicit), False
        cached = read_json(self.root / "web-token.json").get("token", "")
        if claims(cached).get("exp", 0) > time.time() + 3600:
            return cached, True
        token = scrape_web_token(client)
        private_json(self.root / "web-token.json", {"token": token})
        return token, True


def verify_user_token(credentials: Credentials, token: str, *, web: bool) -> str:
    """Check a candidate with Apple before replacing any saved connection."""
    from .api import MusicAPI

    credentials.validate_user_token(token)

    class CandidateCredentials(Credentials):
        def user_token(self):
            return token

        def user_token_source(self):
            return "web" if web else "musickit"

        def developer_token(self, client, force_web=False):
            return credentials.developer_token(client, force_web=web or force_web)

    with httpx.Client(timeout=20) as client:
        api = MusicAPI(CandidateCredentials(credentials.root), client)
        storefront = api.resolve_storefront(strict=True)
        api.request("GET", "/v1/me/library/songs", params={"limit": 1})
        return storefront


def login_server(credentials: Credentials, developer_token: str) -> tuple[HTTPServer, str]:
    """Create a temporary, loopback-only server with a random callback capability."""
    if claims(developer_token).get("iss") == "AMPWebPlay":
        raise MusicError(
            "Apple's public web-player token cannot authorize this local MusicKit page. "
            "Use `apple-music-mcp login --web` to sign in on Apple's website."
        )
    nonce = secrets.token_urlsafe(32)
    landing = f"/{nonce}"
    callback = landing + "/token"
    settings = json.dumps(
        {
            "developerToken": developer_token,
            "app": {"name": "Tomer's Apple Music MCP", "build": "0.1.0"},
        }
    )
    html = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect Apple Music</title>
<style>body{font:17px system-ui;background:#111;color:#eee;max-width:620px;margin:12vh auto;
padding:28px}button{font:inherit;border:0;border-radius:12px;padding:15px 24px;background:#fa365e;
color:white;cursor:pointer}small{color:#aaa}#status{white-space:pre-wrap;line-height:1.6}</style>
<h1>Connect your Apple Music</h1>
<p>Sign in with Apple to let your Hermes agent manage your music library and playlists.</p>
<p>Your password stays with Apple. This local server stores only the music access token.</p>
<button id="connect" disabled>Connect Apple Music</button><p id="status">Loading MusicKit…</p>
<small>You can close this page after the connection succeeds.</small>
<script src="https://js-cdn.music.apple.com/musickit/v3/musickit.js" async></script>
<script>
const status = document.getElementById('status');
const button = document.getElementById('connect');
document.addEventListener('musickitloaded', async () => {
  try { await MusicKit.configure(SETTINGS); button.disabled = false;
    status.textContent = 'Ready. Sign in with the Apple account you use for Music.';
  } catch (error) { status.textContent = 'MusicKit could not load: ' + error.message; }
});
button.onclick = async () => {
  button.disabled = true; status.textContent = 'Waiting for Apple sign-in…';
  try {
    const token = await MusicKit.getInstance().authorize();
    const response = await fetch(CALLBACK, {method: 'POST',
      headers: {'Content-Type':'application/json'}, body: JSON.stringify({token})});
    if (!response.ok) throw new Error(await response.text());
    status.textContent = 'Connected. Hermes can now add catalog songs to your library.';
    button.textContent = 'Connected';
  } catch (error) { status.textContent = 'Sign-in did not complete: ' + error.message;
    button.disabled = false; }
};
</script></html>""".replace("SETTINGS", settings).replace("CALLBACK", json.dumps(callback))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never log callback requests or credentials.

        def _response(self, code: int, body: str, mime: str = "text/plain") -> None:
            encoded = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if (
                self.headers.get("Host") != self.server.expected_host
                or urlsplit(self.path).path != landing
            ):
                self._response(404, "Not found")
                return
            self._response(200, html, "text/html")

        def do_POST(self):
            expected_origin = "http://" + self.server.expected_host
            if (
                self.headers.get("Host") != self.server.expected_host
                or self.path != callback
                or self.headers.get("Origin") != expected_origin
                or self.headers.get("Content-Type") != "application/json"
            ):
                self._response(403, "Rejected")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 20000:
                    raise ValueError
                payload = json.loads(self.rfile.read(length))
                token = payload["token"]
                storefront = verify_user_token(credentials, token, web=False)
                credentials.save_user_token(token, source="musickit")
            except (ValueError, KeyError, TypeError, MusicError):
                self._response(400, "Invalid token")
                return
            self.server.authorized = True
            self.server.storefront = storefront
            self._response(200, "Connected")

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.expected_host = f"127.0.0.1:{server.server_port}"
    server.authorized = False
    server.timeout = 1
    return server, "http://" + server.expected_host + landing
