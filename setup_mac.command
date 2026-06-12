#!/bin/zsh
set -e

cd "$(dirname "$0")"

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

echo "Preparing Timbre Shift for this Mac..."

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is not installed."
  echo "Install Homebrew first, then run this file again:"
  echo "https://brew.sh/zh-cn/"
  read "?Press Enter to close..."
  exit 1
fi

echo "Installing system tools..."
brew install ffmpeg python@3.11

if [ ! -f "$PWD/vendor/seed-vc/inference.py" ]; then
  echo "Seed-VC source is missing. Cloning it now..."
  mkdir -p "$PWD/vendor"
  git clone https://github.com/Plachtaa/seed-vc.git "$PWD/vendor/seed-vc"
fi

echo "Creating Python virtual environment..."
/opt/homebrew/bin/python3.11 -m venv "$PWD/.venv"
source "$PWD/.venv/bin/activate"

echo "Installing Python packages..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$PWD"
python -m pip install demucs torchcodec

if [ -f "$PWD/vendor/seed-vc/requirements-mac.txt" ]; then
  python -m pip install -r "$PWD/vendor/seed-vc/requirements-mac.txt"
elif [ -f "$PWD/vendor/seed-vc/requirements.txt" ]; then
  python -m pip install -r "$PWD/vendor/seed-vc/requirements.txt"
fi

echo ""
echo "Setup finished."
echo "Next: double-click start.command."
read "?Press Enter to close..."
