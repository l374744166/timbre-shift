#!/bin/zsh
set -e

cd "$(dirname "$0")"

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH="$PWD/src"

if [ ! -x "$PWD/.venv/bin/python" ]; then
  echo "Python environment not found."
  echo "Run setup_mac.command first, then run start.command again."
  read "?Press Enter to close..."
  exit 1
fi

if [ ! -f "$PWD/vendor/seed-vc/inference.py" ]; then
  echo "Seed-VC is missing at vendor/seed-vc/inference.py."
  echo "Run setup_mac.command first, then run start.command again."
  read "?Press Enter to close..."
  exit 1
fi

echo "Checking Timbre Shift environment..."
"$PWD/.venv/bin/python" -m timbre_shift.cli check --seed-vc-dir "$PWD/vendor/seed-vc" || true

echo ""
echo "Starting Timbre Shift at http://127.0.0.1:8765/"
(sleep 2 && open "http://127.0.0.1:8765/") >/dev/null 2>&1 &

"$PWD/.venv/bin/python" -m timbre_shift.cli web \
  --host 127.0.0.1 \
  --port 8765 \
  --seed-vc-dir "$PWD/vendor/seed-vc"
