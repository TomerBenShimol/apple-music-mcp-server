"""Nonblocking, human-completed account sign-in for MCP clients."""

from __future__ import annotations

import os
import threading

from .auth import Credentials, MusicError, private_json, read_json
from .browser_login import browser_login

ACTIVE = {"starting", "waiting_for_sign_in"}


class SignInManager:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.state_path = credentials.root / "signin-state.json"
        self.lock_path = credentials.root / "music-signin.lock"
        self.mutex = threading.Lock()
        self.cancelled = threading.Event()
        self.thread: threading.Thread | None = None

    def _acquire(self, *, create: bool) -> int:
        if create:
            self.credentials.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        if create:
            flags |= os.O_CREAT
        fd = os.open(self.lock_path, flags, 0o600)
        try:
            if os.name == "posix":
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def _release(fd: int) -> None:
        # Closing the descriptor releases its OS lock, even on an error path.
        os.close(fd)

    def status(self) -> dict:
        state = read_json(self.state_path) or {"status": "not_started"}
        if state["status"] in ACTIVE:
            if self.thread is not None and self.thread.is_alive():
                return state
            try:
                fd = self._acquire(create=False)
            except BlockingIOError:
                return state  # Another Hermes/ChatGPT process owns the sign-in.
            except FileNotFoundError:
                pass
            else:
                self._release(fd)
            return {
                "status": "interrupted",
                "message": "The sign-in process stopped. Call connect_apple_music again.",
            }
        return state

    def start(self, timeout: int = 900) -> dict:
        with self.mutex:
            if self.thread is not None and self.thread.is_alive():
                return {**self.status(), "already_running": True}
            try:
                fd = self._acquire(create=True)
            except BlockingIOError:
                return {
                    "status": "already_running",
                    "message": "Apple Music sign-in is already running in another MCP client.",
                }
            except OSError as exc:
                raise MusicError("Cannot start sign-in in the local credential directory.") from exc
            self.cancelled = threading.Event()
            try:
                private_json(
                    self.state_path,
                    {
                        "status": "starting",
                        "message": "Starting a local browser for Apple Music sign-in.",
                    },
                )
                self.thread = threading.Thread(
                    target=self._run, args=(fd, timeout), name="apple-music-signin", daemon=True
                )
                self.thread.start()
            except BaseException:
                self._release(fd)
                raise
            return self.status()

    def _ready(self) -> None:
        private_json(
            self.state_path,
            {
                "status": "waiting_for_sign_in",
                "message": "Complete Apple Music sign-in in the browser on this Mac. "
                "Keep passwords and verification codes in Apple's sign-in page. "
                "Call get_status after sign-in to verify library access.",
            },
        )

    def _run(self, fd: int, timeout: int) -> None:
        try:
            try:
                storefront = browser_login(
                    self.credentials,
                    timeout=timeout,
                    on_ready=self._ready,
                    cancelled=self.cancelled,
                )
                state = {"status": "connected", "storefront": storefront}
            except MusicError as exc:
                state = {
                    "status": "cancelled" if self.cancelled.is_set() else "failed",
                    "message": str(exc),
                }
            except Exception:
                # Browser exceptions can include private account URLs. Do not persist them.
                state = {"status": "failed", "message": "Apple Music sign-in could not finish."}
            private_json(self.state_path, state)
        finally:
            self._release(fd)

    def close(self) -> None:
        self.cancelled.set()
        if self.thread is not None:
            # The browser helper closes the window and removes its temporary profile.
            self.thread.join()
