"""Music.app's scripting API, with bounded calls and serialized access."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from importlib.resources import files

from .auth import MusicError

NATIVE_ID = re.compile(r"[0-9a-fA-F]{16}\Z")


class NativeMusic:
    def __init__(self, timeout: float = 25):
        self.timeout = timeout
        self.lock = threading.RLock()

    def call(self, operation: str, **arguments) -> dict:
        if sys.platform != "darwin":
            raise MusicError("The native backend needs macOS. Sign in to use the web backend.")
        for key in ("id",):
            if key in arguments:
                arguments[key] = self.validate_id(arguments[key])
        if "track_ids" in arguments:
            arguments["track_ids"] = [self.validate_id(t) for t in arguments["track_ids"]]
        script = str(files("apple_music_mcp").joinpath("music.js"))
        with self.lock:
            try:
                result = subprocess.run(
                    [
                        "/usr/bin/osascript",
                        "-l",
                        "JavaScript",
                        script,
                        operation,
                        json.dumps(arguments, ensure_ascii=False),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                message = (
                    "Music did not respond. Check for a permission dialog or a dialog in Music. "
                )
                if operation not in {
                    "status",
                    "search",
                    "track",
                    "playlists",
                    "playlist",
                    "playlist_tracks",
                }:
                    message += (
                        "The write outcome is uncertain; inspect the library before retrying. "
                    )
                raise MusicError(
                    message + "Allow the calling app to control Music in macOS "
                    "Settings → Privacy & Security → Automation."
                ) from exc
        if result.returncode:
            detail = result.stderr.strip()
            if "-1743" in detail:
                raise MusicError(
                    "Music automation access is denied. Enable it in macOS Settings → "
                    "Privacy & Security → Automation for the app running Hermes."
                )
            raise MusicError("Music scripting failed: " + detail[:800])
        try:
            return json.loads(result.stdout)
        except ValueError as exc:
            raise MusicError(
                "Music returned an unreadable result. Inspect Music before retrying."
            ) from exc

    def check_access(self) -> dict:
        try:
            return self.call("status")
        except MusicError as exc:
            return {"accessible": False, "error": str(exc)}

    @staticmethod
    def validate_id(value: str) -> str:
        if not NATIVE_ID.fullmatch(value):
            raise MusicError(
                "Native IDs must be 16-digit hexadecimal persistent IDs from these tools."
            )
        return value.upper()
