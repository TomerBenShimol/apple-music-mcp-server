"""User-login service for the existing private ChatGPT tunnel.

The runtime key is stored in macOS Keychain, never in argv, a plist, or a file.
The installed copy and tunnel binary live outside Desktop/iCloud.
"""

from __future__ import annotations

import argparse
import ctypes as ct
import getpass
import json
import os
import plistlib
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

LABEL = "local.apple-music-chatgpt"
SERVICE = "Apple Music — OpenAI tunnel"
ROOT = Path.home() / ".local/share/apple-music-mcp"
HERE = ROOT / "chatgpt"
CLIENT = HERE / "tunnel-client"
PYTHON = ROOT / ".venv/bin/python"
CONFIG_DIR = Path.home() / ".config/apple-music-mcp/chatgpt-profiles"
PROFILE = "apple-music-background"
PROFILE_FILE = CONFIG_DIR / (PROFILE + ".yaml")
FOREGROUND_PROFILE_FILE = CONFIG_DIR / "apple-music-chatgpt.yaml"
ITEM_NOT_FOUND = -25300
PLIST = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
LOGS = Path.home() / ".local/state/apple-music-mcp"
PORT = 61356
DOMAIN = f"gui/{os.getuid()}"
TARGET = f"{DOMAIN}/{LABEL}"


class Keychain:
    """Small ctypes bridge to Apple's SecItem API; no third-party dependency."""

    def __init__(self):
        self.cf = ct.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        self.sec = ct.CDLL("/System/Library/Frameworks/Security.framework/Security")
        signatures = {
            "CFDictionaryCreateMutable": (
                [ct.c_void_p, ct.c_long, ct.c_void_p, ct.c_void_p],
                ct.c_void_p,
            ),
            "CFDictionarySetValue": ([ct.c_void_p, ct.c_void_p, ct.c_void_p], None),
            "CFStringCreateWithCString": ([ct.c_void_p, ct.c_char_p, ct.c_uint32], ct.c_void_p),
            "CFDataCreate": ([ct.c_void_p, ct.c_void_p, ct.c_long], ct.c_void_p),
            "CFDataGetLength": ([ct.c_void_p], ct.c_long),
            "CFDataGetBytePtr": ([ct.c_void_p], ct.c_void_p),
            "CFRelease": ([ct.c_void_p], None),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.cf, name)
            fn.argtypes, fn.restype = args, result
        for name, args in {
            "SecItemAdd": [ct.c_void_p, ct.c_void_p],
            "SecItemUpdate": [ct.c_void_p, ct.c_void_p],
            "SecItemCopyMatching": [ct.c_void_p, ct.POINTER(ct.c_void_p)],
            "SecItemDelete": [ct.c_void_p],
        }.items():
            fn = getattr(self.sec, name)
            fn.argtypes, fn.restype = args, ct.c_int32

    def constant(self, name):
        library = self.cf if name.startswith("kCF") else self.sec
        return ct.c_void_p.in_dll(library, name).value

    @contextmanager
    def query(self, account, *, data=None, retrieve=False, attributes_only=False):
        dictionary = self.cf.CFDictionaryCreateMutable(None, 0, None, None)
        owned = [dictionary]

        def put(key, value):
            self.cf.CFDictionarySetValue(dictionary, self.constant(key), value)

        def string(value):
            ref = self.cf.CFStringCreateWithCString(None, value.encode(), 0x08000100)
            owned.append(ref)
            return ref

        try:
            identity = (
                ()
                if attributes_only
                else (
                    ("kSecClass", self.constant("kSecClassGenericPassword")),
                    ("kSecAttrService", string(SERVICE)),
                    ("kSecAttrAccount", string(account)),
                )
            )
            for key, value in identity:
                put(key, value)
            if data is not None:
                raw = data.encode()
                ref = self.cf.CFDataCreate(None, raw, len(raw))
                owned.append(ref)
                put("kSecValueData", ref)
            if retrieve:
                put("kSecReturnData", self.constant("kCFBooleanTrue"))
                put("kSecMatchLimit", self.constant("kSecMatchLimitOne"))
            yield dictionary
        finally:
            for ref in reversed(owned):
                self.cf.CFRelease(ref)

    @staticmethod
    def check(status):
        if status:
            raise RuntimeError(f"macOS Keychain returned error {status}.")

    def save(self, account, value):
        with self.query(account, data=value) as query:
            status = self.sec.SecItemAdd(query, None)
        if status == -25299:  # Update only our exact service/account entry.
            with self.query(account) as query:
                with self.query(account, data=value, attributes_only=True) as attributes:
                    status = self.sec.SecItemUpdate(query, attributes)
        self.check(status)

    def read_optional(self, account):
        result = ct.c_void_p()
        with self.query(account, retrieve=True) as query:
            status = self.sec.SecItemCopyMatching(query, ct.byref(result))
        if status == ITEM_NOT_FOUND:
            return None
        self.check(status)
        try:
            length = self.cf.CFDataGetLength(result)
            return ct.string_at(self.cf.CFDataGetBytePtr(result), length).decode()
        finally:
            self.cf.CFRelease(result)

    def read(self, account):
        value = self.read_optional(account)
        if value is None:
            raise RuntimeError(f"macOS Keychain returned error {ITEM_NOT_FOUND}.")
        return value

    def delete(self, account):
        with self.query(account) as query:
            status = self.sec.SecItemDelete(query)
        if status != ITEM_NOT_FOUND:
            self.check(status)


def read_settings():
    settings = json.loads(PROFILE_FILE.read_text())
    tunnel_id = settings["control_plane"]["tunnel_id"]
    if not re.fullmatch(r"tunnel_[A-Za-z0-9_-]+", tunnel_id):
        raise RuntimeError("Invalid tunnel ID in the background profile.")
    return settings, tunnel_id


def arguments(action):
    return [
        str(CLIENT),
        action,
        "--profile",
        PROFILE,
        "--profile-dir",
        str(CONFIG_DIR),
        "--mcp.stdio-send-initialized-notification",
        "--mcp.max-concurrent-requests",
        "1",
        "--health.listen-addr",
        f"127.0.0.1:{PORT}",
        "--log.http-raw-unsafe=false",
        "--allow-remote-ui=false",
    ]


def environment(key):
    # No inherited tunnel overrides, proxy settings, or credentials from other apps.
    return {
        "HOME": str(Path.home()),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "LANG": "en_US.UTF-8",
        "APPLE_MUSIC_STOREFRONT": "il",
        "CONTROL_PLANE_API_KEY": key,
    }


def ready():
    # Explicitly bypass proxies for the loopback health request.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{PORT}/readyz", timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def make_plist():
    return {
        "Label": LABEL,
        "ProgramArguments": [str(PYTHON), str(HERE / "chatgpt_service.py"), "run"],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 30,
        "ProcessType": "Background",
        "Umask": 0o077,
        "StandardOutPath": str(LOGS / "chatgpt-tunnel.log"),
        "StandardErrorPath": str(LOGS / "chatgpt-tunnel-error.log"),
    }


def launchctl(*args, check=True):
    # Never print subprocess diagnostics that might unexpectedly contain a secret.
    return subprocess.run(
        ["/bin/launchctl", *args],
        check=check,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_foreground():
    old_client = str(Path.home() / "Desktop/apple-music-mcp/.chatgpt/tunnel-client")
    expected = shlex.join(
        [
            old_client,
            "run",
            "--profile",
            "apple-music-chatgpt",
            "--profile-dir",
            str(CONFIG_DIR),
        ]
    )
    listing = subprocess.check_output(["/bin/ps", "-axo", "pid=,command="], text=True)
    for line in listing.splitlines():
        columns = line.strip().split(maxsplit=1)
        if len(columns) == 2 and columns[1].startswith(expected + " "):
            try:
                os.kill(int(columns[0]), signal.SIGTERM)
            except ProcessLookupError:
                pass


@dataclass(frozen=True)
class Previous:
    key: str | None
    plist: bytes | None


def ensure_background_profile():
    """Derive the background profile from the one connect_chatgpt.py writes."""
    if PROFILE_FILE.exists():
        return
    if not FOREGROUND_PROFILE_FILE.exists():
        raise RuntimeError("Run scripts/connect_chatgpt.py first to create the tunnel profile.")
    fd = os.open(PROFILE_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(FOREGROUND_PROFILE_FILE.read_text())


def prompt_key():
    print("Enable automatic Apple Music connection for ChatGPT.")
    print("Your OpenAI runtime key will be saved in macOS Keychain, never in this project.")
    print("Paste the same OpenAI key used earlier. Characters will stay hidden.")
    key = getpass.getpass("OpenAI runtime API key: ").strip()
    if not key or any(char.isspace() for char in key):
        raise RuntimeError("The key is empty or contains whitespace.")
    return key


def check_key(key):
    subprocess.run(
        arguments("doctor"),
        env=environment(key),
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def prepare_logs():
    LOGS.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("chatgpt-tunnel.log", "chatgpt-tunnel-error.log"):
        fd = os.open(LOGS / name, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
        os.chmod(LOGS / name, 0o600)


def probe_port():
    with socket.socket() as probe:
        # The old agent's listener may still be in TIME_WAIT right after bootout.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", PORT))
        except OSError as error:
            raise RuntimeError(
                "The background health port is in use. Ask Codex to check it."
            ) from error


def wait_until_ready():
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if ready():
            return
        time.sleep(1)
    raise RuntimeError(
        "The background connection was not ready. Any previous background connection was restored."
    )


def activate(keychain, tunnel_id, key):
    keychain.save(tunnel_id, key)
    if keychain.read(tunnel_id) != key:
        raise RuntimeError("Could not verify the saved Keychain entry.")
    prepare_logs()
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    launchctl("bootout", TARGET, check=False)
    probe_port()
    PLIST.write_bytes(plistlib.dumps(make_plist()))
    PLIST.chmod(0o600)
    launchctl("bootstrap", DOMAIN, str(PLIST))
    wait_until_ready()


def restore(keychain, tunnel_id, previous):
    """Put back the key and LaunchAgent that were in place before this install."""
    launchctl("bootout", TARGET, check=False)
    if previous.key is None:
        keychain.delete(tunnel_id)
    else:
        keychain.save(tunnel_id, previous.key)
    if previous.plist is None:
        PLIST.unlink(missing_ok=True)
        return
    PLIST.write_bytes(previous.plist)
    PLIST.chmod(0o600)
    launchctl("bootstrap", DOMAIN, str(PLIST), check=False)


def install():
    if not sys.stdin.isatty():
        raise RuntimeError(
            "Run chatgpt_service.py install in an interactive terminal to enter the key privately."
        )
    ensure_background_profile()
    _, tunnel_id = read_settings()
    if not CLIENT.is_file() or not PYTHON.is_file():
        raise RuntimeError("The installed Apple Music runtime or tunnel client is missing.")
    key = prompt_key()
    check_key(key)
    keychain = Keychain()
    previous = Previous(
        key=keychain.read_optional(tunnel_id),
        plist=PLIST.read_bytes() if PLIST.exists() else None,
    )
    try:
        activate(keychain, tunnel_id, key)
    except BaseException:
        restore(keychain, tunnel_id, previous)
        raise
    stop_foreground()
    print("Connected. Automatic startup is enabled.")
    print("You can close both Terminal windows. Keep your Mac awake and online.")
    return 0


def run():
    os.umask(0o077)
    _, tunnel_id = read_settings()
    key = Keychain().read(tunnel_id)
    # Bound log growth on restarts without retaining a log history.
    for name in ("chatgpt-tunnel.log", "chatgpt-tunnel-error.log"):
        path = LOGS / name
        if path.exists() and path.stat().st_size > 1_000_000:
            with path.open("w"):
                pass
    os.chdir(ROOT)
    os.execve(CLIENT, arguments("run"), environment(key))


def status():
    is_ready = ready()
    print("Connected and ready." if is_ready else "Background connection is not ready.")
    return 0 if is_ready else 1


def stop():
    launchctl("bootout", TARGET, check=False)
    print("Stopped. Run 'start' to enable the background connection again.")
    return 0


def start():
    launchctl("bootstrap", DOMAIN, str(PLIST))
    print("Background connection starting.")
    return 0


ACTIONS: dict[str, Callable[[], int]] = {
    "install": install,
    "run": run,
    "status": status,
    "stop": stop,
    "start": start,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=sorted(ACTIONS))
    return ACTIONS[parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        raise SystemExit(130) from None
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        # Exceptions from our helpers contain no key, command output, or environment.
        print(f"Apple Music connection: {error}", file=sys.stderr)
        raise SystemExit(1) from None
