# macOS installation notes

For Windows, use the [PowerShell installation guide](windows.md).

[Back to the README](../README.md#quick-start)

The main setup uses Python 3.11 or newer in a virtual environment. Upgrade pip
before installing so it can recognize current wheel formats:

```bash
.venv/bin/python -m pip install --upgrade pip
```

## Intel Macs

A fresh install on an Intel Mac can fail while building the `cryptography`
dependency, with an error about missing OpenSSL headers or libraries. Since
version 49, that project no longer publishes Intel macOS wheels or tests that
platform. See its [release notes](https://cryptography.io/en/49.0.0/changelog/).

Building from source needs Xcode Command Line Tools, Rust 1.83 or newer, and
OpenSSL. If you use Homebrew, follow the dependency's
[macOS build instructions](https://cryptography.io/en/50.0.2/installation/#building-cryptography-on-macos):

```bash
xcode-select --install
brew install openssl@3 rust
```

If Xcode Command Line Tools are already installed, you can skip the first command.
Run these from the cloned repository after creating `.venv`:

```bash
OPENSSL_DIR="$(brew --prefix openssl@3)" .venv/bin/python -m pip install -e '.[browser]'
.venv/bin/apple-music-mcp doctor --probe
```

Use this install command in place of the plain pip command in the quick start.
Then continue with browser installation, Apple Music sign-in, and your client setup.
These build tools are an extra requirement for Intel Macs; neither Docker nor
Linux is needed.

A fresh Python 3.13 install on an Intel Mac was checked on 2026-10-16 using
OpenSSL 3.5.9 built in a temporary directory. MCP discovery returned all 17 tools,
and all six installers wrote temporary configuration files successfully. That
check didn't sign in to an account or test inside the client applications.

## Apple Silicon

The current `cryptography` release has Apple Silicon wheels. Use an ARM64 Python
and the regular install command in the README. A Python running under Rosetta can
be treated as Intel even on an Apple Silicon Mac; check it with:

```bash
.venv/bin/python -c 'import platform; print(platform.machine())'
```

If it prints `x86_64`, use the Intel build steps or recreate the virtual environment
with an ARM64 Python. If pip still tries to compile a dependency, check that your
Python version and macOS version have compatible wheels for that dependency.
