#!/bin/zsh
project_dir=${0:A:h}
runtime_dir="$HOME/.local/share/tomer-apple-music-mcp"
exec "$runtime_dir/.venv/bin/python" "$project_dir/scripts/connect_chatgpt.py"
