"""Human sign-in on Apple's own website, using an isolated temporary browser.

This helper never fills credentials or clicks account prompts. The user signs in
directly with Apple. Only the Music User Token is saved after read-only API checks;
the temporary browser profile, including Apple's other session cookies, is removed.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event

from .auth import Credentials, MusicError, TransientMusicError, verify_user_token


def music_token(cookies: list[dict]) -> str | None:
    """Select only Apple's music credential; never return other account cookies."""
    for cookie in cookies:
        domain = cookie.get("domain", "").lstrip(".")
        if (
            cookie.get("name") == "media-user-token"
            and domain in {"apple.com", "music.apple.com"}
            and cookie.get("secure") is True
        ):
            token = cookie.get("value")
            if token:
                Credentials.validate_user_token(token)
                return token
    return None


PROFILE_PREFIX = ".signin-"
RETRY_PAUSE_MS = 10000


def sweep_profiles(root: Path) -> None:
    """Remove browser profiles an interrupted sign-in left behind; callers hold the sign-in lock."""
    for stale in root.glob(PROFILE_PREFIX + "*"):
        shutil.rmtree(stale, ignore_errors=True)


def ensure_window(context, cancelled: Event | None) -> None:
    if cancelled is not None and cancelled.is_set():
        raise MusicError("Apple Music sign-in was cancelled.")
    if not context.pages:
        raise MusicError("The sign-in window was closed. Run login again.")


def signed_in_storefront(credentials: Credentials, context) -> str | None:
    token = music_token(context.cookies("https://music.apple.com"))
    if not token:
        return None
    try:
        storefront = verify_user_token(credentials, token, web=True)
    except TransientMusicError:
        context.pages[0].wait_for_timeout(RETRY_PAUSE_MS)
        return None
    credentials.save_user_token(token, source="web")
    return storefront


def browser_login(
    credentials: Credentials,
    timeout: int = 600,
    *,
    on_ready: Callable[[], None] | None = None,
    cancelled: Event | None = None,
) -> str:
    try:
        from playwright.sync_api import Error as BrowserError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise MusicError(
            "Web sign-in needs the optional browser helper. Install "
            "`tomer-apple-music-mcp[browser]`; if Chrome is not installed, "
            "also run `playwright install chromium`."
        ) from exc

    credentials.root.mkdir(parents=True, exist_ok=True, mode=0o700)
    channel = (
        "chrome"
        if sys.platform == "darwin" and Path("/Applications/Google Chrome.app").exists()
        else None
    )
    deadline = time.monotonic() + max(1, min(timeout, 3600))
    try:
        with tempfile.TemporaryDirectory(prefix=PROFILE_PREFIX, dir=credentials.root) as profile:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    profile,
                    channel=channel,
                    headless=False,
                    chromium_sandbox=True,
                )
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto(
                        "https://music.apple.com/", wait_until="domcontentloaded", timeout=20000
                    )
                    if on_ready:
                        on_ready()
                    print(
                        "In the separate browser window, click Sign In and finish Apple's "
                        "sign-in. Your password stays with Apple. Waiting for music access…",
                        file=sys.stderr,
                        flush=True,
                    )
                    while time.monotonic() < deadline:
                        ensure_window(context, cancelled)
                        storefront = signed_in_storefront(credentials, context)
                        if storefront:
                            return storefront
                        # Dispatch browser events without navigating away from sign-in/2FA.
                        context.pages[0].wait_for_timeout(1000)
                    raise MusicError("Sign-in timed out. Run login again when you are ready.")
                finally:
                    context.close()
    except BrowserError as exc:
        # Browser error text can contain account URLs; don't expose it in logs/chat.
        raise MusicError(
            "The sign-in browser could not open or was closed. Run login again. "
            "If Chrome is unavailable, run `playwright install chromium` first."
        ) from exc
