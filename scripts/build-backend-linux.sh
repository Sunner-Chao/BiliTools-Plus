#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT_DIR/app/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing Python venv: $PYTHON" >&2
  exit 1
fi

cd "$ROOT_DIR"
"$PYTHON" -m pip install -U pip pyinstaller
"$PYTHON" -m pip install -r requirements.txt

"$PYTHON" -m PyInstaller \
  --clean \
  --noconfirm \
  --name backend \
  --paths "$ROOT_DIR" \
  --hidden-import aiosqlite \
  --hidden-import sqlalchemy.dialects.sqlite.aiosqlite \
  --hidden-import qrcode.image.pil \
  --collect-submodules app \
  --collect-all pydantic \
  --collect-all pydantic_settings \
  app/packaging/backend_launcher.py

echo "Linux backend built at: $ROOT_DIR/dist/backend/backend"
