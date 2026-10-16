import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is needed for the JXA mock harness")
ROOT = Path(__file__).resolve().parents[1]


def exercise(scenario):
    result = subprocess.run(
        [
            NODE,
            str(ROOT / "tests/music_harness.js"),
            str(ROOT / "src/apple_music_mcp/music.js"),
            scenario,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def test_playlist_uses_jxa_class_name():
    result = exercise("create")
    assert "error" not in result
    assert "New" in result["playlists"]


def test_update_preview_preserves_name_and_rejects_protected_playlists():
    preview = exercise("update-preview")
    assert preview["result"]["dry_run"] is True
    assert preview["name"] == "Original"
    assert "ordinary user playlists" in exercise("protected")["error"]


def test_import_without_confirmed_results_reports_unconfirmed_files():
    result = exercise("import")
    assert result["result"] == {"added": [], "unconfirmed": 2}


def test_native_add_failure_reports_completed_ids():
    result = exercise("partial-add")
    assert result["original"] == ["A"]
    assert 'Completed additions: ["A"]' in result["error"]


def test_native_library_removal_failure_reports_completed_ids():
    result = exercise("partial-remove")
    assert result["library"] == ["B"]
    assert 'Completed removals: ["A"]' in result["error"]


def test_incomplete_backup_is_removed_before_original_is_touched():
    result = exercise("backup-failure")
    assert result["original"] == ["A", "B"]
    assert result["playlists"] == ["Original"]
    assert "playlist was not changed" in result["error"]


def test_failed_rewrite_retains_recovery_playlist():
    result = exercise("rewrite-failure")
    assert "Recovery" in result["playlists"]
    assert "saved in playlist Recovery" in result["error"]


def test_successful_reorder_verifies_order_and_removes_recovery_copy():
    result = exercise("reorder")
    assert result["original"] == ["B", "A"]
    assert result["playlists"] == ["Original"]
    assert result["result"]["changed"] is True
