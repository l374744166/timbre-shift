#!/bin/zsh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%d-%H%M%S)"
DIST="$ROOT/dist"
PACKAGE="$DIST/timbre-shift-portable-$STAMP.zip"

mkdir -p "$DIST"

echo "Creating portable package:"
echo "$PACKAGE"

zip -r "$PACKAGE" . \
  -x ".git/*" \
  -x ".venv/*" \
  -x ".venv-py39-backup/*" \
  -x "dist/*" \
  -x "data/raw/*" \
  -x "data/processed/*" \
  -x "data/cache/*" \
  -x "data/reference_voice/*" \
  -x "data/songs/*" \
  -x "outputs/*" \
  -x "logs/*" \
  -x "__pycache__/*" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x ".DS_Store"

echo "Done."
