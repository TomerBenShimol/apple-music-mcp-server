#!/bin/zsh
project_dir=${0:A:h}
runtime_dir="$HOME/.local/share/apple-music-mcp"
if [[ -x "$runtime_dir/.venv/bin/apple-music-mcp" ]]; then
  exec "$runtime_dir/.venv/bin/apple-music-mcp" login --web --timeout 900
fi
exec "$project_dir/.venv/bin/apple-music-mcp" login --web --timeout 900
