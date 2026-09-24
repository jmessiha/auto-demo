#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  VENV_DIR="$ROOT_DIR/.venv-mlx"
  REQUIREMENTS="$ROOT_DIR/requirements-mlx.txt"
  BACKEND="mlx"
else
  VENV_DIR="$ROOT_DIR/.venv"
  REQUIREMENTS="$ROOT_DIR/requirements-pytorch.txt"
  BACKEND="pytorch"
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS"
npm install --prefix "$ROOT_DIR"

printf 'Ready: %s\n' "$ROOT_DIR"
printf 'Backend: %s\n' "$BACKEND"
printf 'Python: %s\n' "$VENV_DIR/bin/python"
printf 'Node: %s\n' "$ROOT_DIR/node_modules/.bin"
