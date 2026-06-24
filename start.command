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
PORT="${TIMBRE_SHIFT_PORT:-8767}"
HOST="${TIMBRE_SHIFT_HOST:-0.0.0.0}"
LOCAL_URL="http://127.0.0.1:${PORT}/"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"

echo "Starting Timbre Shift at ${LOCAL_URL}"
if [ -n "$LAN_IP" ]; then
  echo "Same-network access: http://${LAN_IP}:${PORT}/"
fi
(sleep 2 && open "$LOCAL_URL") >/dev/null 2>&1 &

"$PWD/.venv/bin/python" -m timbre_shift.cli web \
  --host "$HOST" \
  --port "$PORT" \
  --seed-vc-dir "$PWD/vendor/seed-vc"
