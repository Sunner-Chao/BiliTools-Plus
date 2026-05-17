#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/build-backend-linux.sh"
"$ROOT_DIR/scripts/prepare-backend-resources.sh"

cd "$ROOT_DIR/desktop"
env -u ELECTRON_RUN_AS_NODE npm run build:electron
env -u ELECTRON_RUN_AS_NODE ./node_modules/.bin/electron-builder --linux AppImage --x64

echo "Linux package output: $ROOT_DIR/desktop/dist"
