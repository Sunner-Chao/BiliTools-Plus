#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_VERSION="3.11.9"
EMBED_URL="https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-embed-amd64.zip"
BUILD_DIR="$ROOT_DIR/build/windows-portable-backend"
PY_DIR="$BUILD_DIR/python"
WHEEL_DIR="$ROOT_DIR/build/windows-wheels"

rm -rf "$BUILD_DIR" "$WHEEL_DIR" "$ROOT_DIR/desktop/build/backend"
mkdir -p "$PY_DIR" "$WHEEL_DIR" "$BUILD_DIR" "$ROOT_DIR/desktop/build/backend"

if [[ ! -f "$ROOT_DIR/build/python-${PY_VERSION}-embed-amd64.zip" ]]; then
  mkdir -p "$ROOT_DIR/build"
  curl -L "$EMBED_URL" -o "$ROOT_DIR/build/python-${PY_VERSION}-embed-amd64.zip"
fi

python3 - <<PY
from pathlib import Path
from zipfile import ZipFile
zip_path = Path("$ROOT_DIR/build/python-${PY_VERSION}-embed-amd64.zip")
target = Path("$PY_DIR")
with ZipFile(zip_path) as zf:
    zf.extractall(target)
PY

python3 -m pip download \
  --dest "$WHEEL_DIR" \
  --only-binary=:all: \
  --platform win_amd64 \
  --implementation cp \
  --python-version 311 \
  --abi cp311 \
  "fastapi==0.115.0" \
  "uvicorn==0.30.6" \
  "pydantic==2.9.2" \
  "pydantic-settings==2.5.2" \
  "sqlalchemy==2.0.35" \
  "aiosqlite==0.20.0" \
  "httpx[socks]==0.27.2" \
  "python-jose[cryptography]==3.3.0" \
  "passlib[bcrypt]==1.7.4" \
  "python-multipart==0.0.12" \
  "qrcode[pil]==7.4.2" \
  "websockets==13.0.1" \
  "requests==2.32.3"

mkdir -p "$PY_DIR/Lib/site-packages"
python3 - <<PY
from pathlib import Path
from zipfile import ZipFile
site = Path("$PY_DIR/Lib/site-packages")
for wheel in Path("$WHEEL_DIR").glob("*.whl"):
    with ZipFile(wheel) as zf:
        zf.extractall(site)
PY

cat > "$PY_DIR/python311._pth" <<'EOF'
python311.zip
.
Lib\site-packages
..\
import site
EOF

rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' "$ROOT_DIR/app/" "$BUILD_DIR/app/"
for item in config cookies execute captcha_images javascript others data; do
  if [[ -e "$ROOT_DIR/$item" ]]; then
    mkdir -p "$BUILD_DIR/$item"
    rsync -a --delete "$ROOT_DIR/$item/" "$BUILD_DIR/$item/"
  fi
done

cp -R "$BUILD_DIR/." "$ROOT_DIR/desktop/build/backend/"

cd "$ROOT_DIR/desktop"
env -u ELECTRON_RUN_AS_NODE npm run build:electron
CSC_IDENTITY_AUTO_DISCOVERY=false env -u ELECTRON_RUN_AS_NODE ./node_modules/.bin/electron-builder --win zip --x64

echo "Windows portable package output: $ROOT_DIR/desktop/dist"
