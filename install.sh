#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./install.sh

SCRIPT_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
RUN_SH="$SCRIPT_DIR/run.sh"
CFG_EXAMPLE="$SCRIPT_DIR/config.rc.example"
CFG="$SCRIPT_DIR/config.rc"

# Checks
if [[ ! -f "$RUN_SH" ]]; then
  echo "run.sh not found next to install.sh"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Please install Python 3.9+."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "WARNING: ffmpeg not found in PATH. Please install via your package manager."
fi

# Create venv
if [[ ! -d "$VENV_DIR" ]]; then
  echo "-> Creating venv: $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Upgrade pip/setuptools/wheel
python -m pip install --upgrade pip setuptools wheel

# Install whisperx and pyannote.audio
echo "-> Installing whisperx"
pip install whisperx

echo "-> Installing pyannote.audio for speaker recognition"
pip install pyannote.audio

# Config
if [[ -f "$CFG" ]]; then
  echo "-> config.rc already exists — leaving it."
elif [[ -f "$CFG_EXAMPLE" ]]; then
  cp "$CFG_EXAMPLE" "$CFG"
  echo "-> Created config.rc from config.rc.example"
else
  cat >"$CFG" <<'EOF'
export HF_TOKEN="hf_xxx"
export WHX_LANGUAGE="ru"

# Speaker Recognition Settings
export WHX_ENABLE_SPEAKER_MATCHING="false"
export WHX_SPEAKER_THRESHOLD="0.75"
EOF
  echo "-> Created default config.rc"
fi

# Add alias to ~/.bashrc
BASHRC="$HOME/.bashrc"
ALIAS_LINE="alias whx=\"$RUN_SH\""

if ! grep -Fxq "$ALIAS_LINE" "$BASHRC"; then
  echo "$ALIAS_LINE" >> "$BASHRC"
  echo "-> Added alias to $BASHRC"
else
  echo "-> Alias already exists in $BASHRC"
fi

echo
echo "Installation complete."
echo "venv: $VENV_DIR"
echo "whisperx: $VENV_DIR/bin/whisperx"
echo
echo "Next steps:"
echo "  1) Edit config: $CFG"
echo "  2) Reload your shell or run: source ~/.bashrc"
echo "  3) Test run:"
echo "       whx /path/to/media.mkv"
echo
echo "Done."
