"""OS locks shared by sign-in and music edits.

Lock files stay on disk: deleting them could let processes lock different files
at the same path. Closing the descriptor also releases its OS lock.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

WINDOWS = os.name == "nt"


def open_lock(path: Path, *, create: bool = True) -> int:
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags |= os.O_CREAT
    return os.open(path, flags, 0o600)


def try_lock(fd: int) -> None:
    if WINDOWS:
        import msvcrt

        # Windows permits locking beyond EOF, so empty lock files need no writes.
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise BlockingIOError(exc.errno, "Another process holds the lock.") from None
            raise
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def release_lock(fd: int) -> None:
    try:
        if WINDOWS:
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
