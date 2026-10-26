"""Serialize edits across local MCP client processes."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from .auth import MusicError
from .process_lock import open_lock, release_lock, try_lock


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
            if self.depth == 0:
                self._acquire_file()
            self.depth += 1
            return self
        except BaseException:
            self._abort_acquire()
            raise

    def _abort_acquire(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.thread.release()

    def _acquire_file(self):
        self.fd = open_lock(self.path)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                try_lock(self.fd)
                return
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise MusicError(
                        "Another music edit is running. Wait for it to finish, then retry."
                    ) from None
                time.sleep(0.05)

    def __exit__(self, *args):
        try:
            self.depth -= 1
            if self.depth == 0 and self.fd is not None:
                fd, self.fd = self.fd, None
                release_lock(fd)
        finally:
            self.thread.release()
