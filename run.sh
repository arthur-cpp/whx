#!/usr/bin/env bash
set -euo pipefail

# Get directory of this script (resolves symlinks too)
SCRIPT_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"

# Assume venv is in subdir "venv" relative to script
VENV_DIR="$SCRIPT_DIR/venv"

if [ -x "$VENV_DIR/bin/whisperx" ]; then
  WHISPERX_BIN="$VENV_DIR/bin/whisperx"
else
  WHISPERX_BIN="$(command -v whisperx || true)"
fi

if [ -z "$WHISPERX_BIN" ]; then
  echo "whisperx not found (looked in $VENV_DIR and PATH)"
  exit 1
fi

# Load external config if exists
CONFIG_FILE="$SCRIPT_DIR/config.rc"
if [ -f "$CONFIG_FILE" ]; then
  # shellcheck source=/dev/null
  source "$CONFIG_FILE"
fi

# Usage: ./run.sh path/to/media.(wav|mkv|mp4|mp3|...)
if [ $# -lt 1 ]; then
  echo "Usage: $0 path/to/media"
  exit 1
fi

INPUT="$1"

# Check prerequisites
if [ ! -f "$INPUT" ]; then
  echo "File '$INPUT' not found"
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found in PATH"
  exit 1
fi
if ! command -v whisperx >/dev/null 2>&1; then
  echo "whisperx not found in PATH"
  exit 1
fi



# Output directory = input file directory
OUT_DIR="$(dirname "$INPUT")"
BASENAME="$(basename "$INPUT")"
STEM="${BASENAME%.*}"
EXT="${BASENAME##*.}"
EXT_LOWER="${EXT,,}"

# Suppress noisy logs from Python/HF/transformers
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TRANSFORMERS_VERBOSITY=error
export TOKENIZERS_PARALLELISM=false
export PYTHONWARNINGS=ignore

# Helper functions
is_video_ext() {
  case "$1" in
    mkv|mp4|mov|avi|webm|m4v|flv|ts|mpeg|mpg) return 0 ;;
    *) return 1 ;;
  esac
}
is_audio_ext() {
  case "$1" in
    wav|mp3|m4a|flac|ogg|opus|aac|wma) return 0 ;;
    *) return 1 ;;
  esac
}

# Temp files
RAW_WAV="$OUT_DIR/${STEM}_raw.wav"              # extracted from video if needed
PREP_WAV="$OUT_DIR/${STEM}_16k_mono.wav"        # resampled mono 16k PCM
NORM_WAV="$OUT_DIR/${STEM}_16k_mono_norm.wav"   # normalized audio

cleanup() {
  rm -f "$RAW_WAV" "$PREP_WAV" "$NORM_WAV" || true
}
trap cleanup EXIT

SRC_FOR_PREP="$INPUT"

# 1) Extract audio if input is video or unknown
echo "Extracting audio from $INPUT.."
if is_video_ext "$EXT_LOWER"; then
  ffmpeg -hide_banner -loglevel error -y -i "$INPUT" -vn -ac 2 -ar 48000 -c:a pcm_s16le "$RAW_WAV"
  SRC_FOR_PREP="$RAW_WAV"
elif ! is_audio_ext "$EXT_LOWER"; then
  ffmpeg -hide_banner -loglevel error -y -i "$INPUT" -vn -ac 2 -ar 48000 -c:a pcm_s16le "$RAW_WAV"
  SRC_FOR_PREP="$RAW_WAV"
fi

# 2) Convert to mono 16 kHz 16-bit PCM
echo "Converting to mono 16 kHz 16-bit PCM.."
ffmpeg -hide_banner -loglevel error -y -i "$SRC_FOR_PREP" -ac 1 -ar 16000 -c:a pcm_s16le "$PREP_WAV"

# 3) Light loudness normalization
echo "Light loudness normalization.."
ffmpeg -hide_banner -loglevel error -y -i "$PREP_WAV" -af "loudnorm" "$NORM_WAV"

# 4) Run whisperx on normalized audio
#    Show only progress lines (>>Performing ...)
echo "Running $WHISPERX_BIN on $NORM_WAV.."
"$WHISPERX_BIN" "$NORM_WAV" \
  --model large-v3 \
  --diarize \
  --highlight_words True \
  --output_format txt \
  --output_dir "$OUT_DIR" \
  --verbose False \
  --print_progress True \
  --language "${WHX_LANGUAGE:-ru}" \
  --hf_token="${HF_TOKEN:-}"
##  2> >(awk '/^>>/ { print; fflush(); }' >&2)

# 5) Rename final transcript to match input name
FINAL_TXT="${OUT_DIR}/${STEM}.txt"
mv -f "${OUT_DIR}/$(basename "$NORM_WAV" .wav).txt" "$FINAL_TXT"

echo "Final result: $FINAL_TXT"
