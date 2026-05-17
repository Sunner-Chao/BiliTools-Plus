#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$ROOT_DIR/desktop/build/backend"

rm -rf "$TARGET"
mkdir -p "$TARGET"

if [[ -d "$ROOT_DIR/dist/backend" ]]; then
  cp -R "$ROOT_DIR/dist/backend/." "$TARGET/"
fi

for item in config cookies execute captcha_images javascript others data; do
  if [[ -e "$ROOT_DIR/$item" ]]; then
    mkdir -p "$TARGET/$item"
    cp -R "$ROOT_DIR/$item/." "$TARGET/$item/"
  fi
done

echo "Backend resources prepared at: $TARGET"
