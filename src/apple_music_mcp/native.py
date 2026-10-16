"""Music.app's scripting API, with bounded calls and serialized access."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from importlib.resources import files

from .auth import MusicError

NATIVE_ID = re.compile(r"[0-9a-fA-F]{16}\Z")
READ_ONLY = frozenset({"status", "search", "track", "playlists", "playlist", "playlist_tracks"})
BASE_TIMEOUT = 25.0
MAX_TIMEOUT = 1800.0
# Reorder sends about four Apple Events per track; the other batches one or two.
PER_TRACK = {"reorder": 1.0, "add": 0.5, "remove": 0.5, "remove_library": 0.5}
UNCERTAIN = "The write outcome is uncertain; inspect the library before retrying. "
AUTOMATION = (
    "Allow the calling app to control Music in macOS Settings → Privacy & Security → Automation."
)
DENIED = (
    "Music automation access is denied. Enable it in macOS Settings → "
    "Privacy & Security → Automation for the app running this MCP server."
)


def timeout_for(operation: str, arguments: dict, base: float) -> float:
    tracks = len(arguments.get("track_ids", ()))
    return min(base + PER_TRACK.get(operation, 0.0) * tracks, MAX_TIMEOUT)


def recovery_name(playlist_id: str) -> str:
    return f"MCP recovery {playlist_id.upper()} {time.strftime('%Y%m%d-%H%M%S')}"


def uncertainty(operation: str) -> str:
    return "" if operation in READ_ONLY else UNCERTAIN


def recovery_hint(arguments: dict) -> str:
    name = arguments.get("backup_name")
    return f"Original contents may be saved in playlist '{name}'. " if name else ""


def parse_output(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except ValueError as exc:
        raise MusicError(
            "Music returned an unreadable result. Inspect Music before retrying."
        ) from exc


class NativeMusic:
    def __init__(self, timeout: float = BASE_TIMEOUT):
        self.timeout = timeout
        self.lock = threading.RLock()

    def call(self, operation: str, **arguments) -> dict:
        if sys.platform != "darwin":
            raise MusicError("The native backend needs macOS. Sign in to use the web backend.")
        result = self.run_script(operation, self.validated(arguments))
        return self.interpret(operation, result)

    def check_access(self) -> dict:
        try:
            return self.call("status")
        except MusicError as exc:
            return {"accessible": False, "error": str(exc)}

    def validated(self, arguments: dict) -> dict:
        ids = {"id": self.validate_id(arguments["id"])} if "id" in arguments else {}
        tracks = (
            {"track_ids": [self.validate_id(t) for t in arguments["track_ids"]]}
            if "track_ids" in arguments
            else {}
        )
        return {**arguments, **ids, **tracks}

    def run_script(self, operation: str, arguments: dict) -> subprocess.CompletedProcess:
        script = str(files("apple_music_mcp").joinpath("music.js"))
        command = [
            "/usr/bin/osascript",
            "-l",
            "JavaScript",
            script,
            operation,
            json.dumps(arguments, ensure_ascii=False),
        ]
        with self.lock:
            try:
                return subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout_for(operation, arguments, self.timeout),
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise MusicError(
                    "Music did not respond. Check for a permission dialog or a dialog in Music. "
                    + uncertainty(operation)
                    + recovery_hint(arguments)
                    + AUTOMATION
                ) from exc

    @staticmethod
    def interpret(operation: str, result: subprocess.CompletedProcess) -> dict:
        detail = result.stderr.strip()
        match result.returncode:
            case 0:
                return parse_output(result.stdout)
            case _ if "-1743" in detail:
                raise MusicError(DENIED)
            case _:
                raise MusicError("Music scripting failed: " + uncertainty(operation) + detail[:800])

    @staticmethod
    def validate_id(value: str) -> str:
        if not NATIVE_ID.fullmatch(value):
            raise MusicError(
                "Native IDs must be 16-digit hexadecimal persistent IDs from these tools."
            )
        return value.upper()
