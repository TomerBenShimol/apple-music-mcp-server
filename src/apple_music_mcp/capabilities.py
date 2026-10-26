"""Capabilities of the machine running the MCP server."""

import sys

NATIVE_TOOLS = ("reorder_playlist", "import_audio_files")


def supports_native() -> bool:
    return sys.platform == "darwin"


def capabilities() -> dict:
    native = supports_native()
    return {
        "platform": sys.platform,
        "native_backend_available": native,
        "unavailable_tools": [] if native else list(NATIVE_TOOLS),
    }
