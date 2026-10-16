import os
import subprocess
import sys

import pytest

from apple_music_mcp.auth import MusicError
from apple_music_mcp.locking import MusicEditLock


@pytest.mark.skipif(os.name != "posix", reason="POSIX shared edit lock")
def test_nested_lock_keeps_other_clients_excluded_until_outer_exit(tmp_path):
    first = MusicEditLock(tmp_path)
    second = MusicEditLock(tmp_path, timeout=0.01)
    with first:
        with first:
            pass
        with pytest.raises(MusicError, match="Another music edit"):
            with second:
                pytest.fail("A second MCP process must wait for the whole edit")
    with second:
        assert second.fd is not None
    assert first.fd is None and second.fd is None
    assert first.path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX shared edit lock")
def test_another_process_cannot_edit_while_hermes_holds_lock(tmp_path):
    program = """
import sys
from pathlib import Path
from apple_music_mcp.auth import MusicError
from apple_music_mcp.locking import MusicEditLock
try:
    with MusicEditLock(Path(sys.argv[1]), timeout=0.05):
        sys.exit(1)
except MusicError:
    sys.exit(0)
"""
    with MusicEditLock(tmp_path):
        result = subprocess.run(
            [sys.executable, "-c", program, str(tmp_path)], timeout=5, check=False
        )
    assert result.returncode == 0
