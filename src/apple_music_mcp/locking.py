"""Serialize edits across the Hermes and ChatGPT MCP processes on this Mac."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from .auth import MusicError


class MusicEditLock:
    def __init__(self, root: Path, timeout: float = 30):
        self.path = root / "music-edit.lock"
        self.timeout = timeout
        self.thread = threading.RLock()
        self.depth = 0
        self.fd: int | None = None

    def __enter__(self):
        if not self.thread.acquire(timeout=self.timeout):
            raise MusicError("Another music edit is running. Wait for it to finish, then retry.")
        try:
            if self.depth == 0 and os.name == "posix":
                import fcntl

                self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                self.fd = os.open(
                    self.path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
                )
                deadline = time.monotonic() + self.timeout
                while True:
                    try:
                        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise MusicError(
                                "Another music edit is running. Wait for it to finish, then retry."
                            ) from None
                        time.sleep(0.05)
            self.depth += 1
            return self
        except BaseException:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            self.thread.release()
            raise

    def __exit__(self, *args):
        try:
            self.depth -= 1
            if self.depth == 0 and self.fd is not None:
                import fcntl

                try:
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
                finally:
                    os.close(self.fd)
                    self.fd = None
        finally:
            self.thread.release()
