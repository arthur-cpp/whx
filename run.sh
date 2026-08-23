#!/usr/bin/env bash
set -euo pipefail

# 1. Paths and basic setup
SCRIPT_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
SPEAKER_DIR="$SCRIPT_DIR/speakers/data"
CONFIG_FILE="$SCRIPT_DIR/config.rc"

# 2. Load external config FIRST to allow it to set environment variables
if [ -f "$CONFIG_FILE" ]; then
  # shellcheck source=/dev/null
  source "$CONFIG_FILE"
fi

# 3. Initialize variables from environment (now they include values from config.rc)
# Priority: CLI Flag > Environment > Config File > Default
ENABLE_SPEAKER_MATCHING="${WHX_ENABLE_SPEAKER_MATCHING:-false}"
WHX_LANGUAGE="${WHX_LANGUAGE:-ru}"
WHX_SPEAKER_THRESHOLD="${WHX_SPEAKER_THRESHOLD:-0.75}"

# 4. Command line argument parsing (Highest priority)
POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
  case $1 in
    -m|--match)
      ENABLE_SPEAKER_MATCHING="true"
      shift
      ;;
    -nm|--no-match)
      ENABLE_SPEAKER_MATCHING="false"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [options] path/to/file"
      echo "Options:"
      echo "  -m,  --match     Enable speaker matching"
      echo "  -nm, --no-match  Disable speaker matching"
      exit 0
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}"

if [ $# -lt 1 ]; then
  echo "Error: No input file specified."
  exit 1
fi

INPUT="$1"

# 5. Environment and binary checks
if [ -x "$VENV_DIR/bin/whisperx" ]; then
  WHISPERX_BIN="$VENV_DIR/bin/whisperx"
else
  WHISPERX_BIN="$(command -v whisperx || true)"
fi

if [ -z "$WHISPERX_BIN" ]; then
  echo "whisperx not found"
  exit 1
fi

if [ ! -f "$INPUT" ]; then
  echo "File '$INPUT' not found"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found"
  exit 1
fi

# 6. Path preparation
OUT_DIR="$(dirname "$INPUT")"
BASENAME="$(basename "$INPUT")"
STEM="${BASENAME%.*}"
EXT="${BASENAME##*.}"
EXT_LOWER="${EXT,,}"

RAW_WAV="$OUT_DIR/${STEM}_raw.wav"
PREP_WAV="$OUT_DIR/${STEM}_16k_mono.wav"
NORM_WAV="$OUT_DIR/${STEM}_16k_mono_norm.wav"

# Suppress logs
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TRANSFORMERS_VERBOSITY=error
export TOKENIZERS_PARALLELISM=false
export PYTHONWARNINGS=ignore

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

cleanup() {
  rm -f "$RAW_WAV" "$PREP_WAV" "$NORM_WAV" || true
  if [ -d "$HOME/nltk_data" ]; then
      rm -rf "$HOME/nltk_data"
  fi
}
trap cleanup EXIT

# 7. Audio processing
SRC_FOR_PREP="$INPUT"

echo "1/4 Extracting audio..."
if is_video_ext "$EXT_LOWER" || ! is_audio_ext "$EXT_LOWER"; then
  ffmpeg -hide_banner -loglevel error -y -i "$INPUT" -vn -ac 2 -ar 48000 -c:a pcm_s16le "$RAW_WAV"
  SRC_FOR_PREP="$RAW_WAV"
fi

echo "2/4 Converting..."
ffmpeg -hide_banner -loglevel error -y -i "$SRC_FOR_PREP" -ac 1 -ar 16000 -c:a pcm_s16le "$PREP_WAV"

echo "3/4 Normalizing..."
ffmpeg -hide_banner -loglevel error -y -i "$PREP_WAV" -af "loudnorm" "$NORM_WAV"

# 8. Run WhisperX
echo "4/4 Running WhisperX (Language: $WHX_LANGUAGE)..."
"$WHISPERX_BIN" "$NORM_WAV" \
  --model large-v3 \
  --diarize \
  --highlight_words True \
  --output_format json \
  --output_dir "$OUT_DIR" \
  --verbose False \
  --print_progress True \
  --language "$WHX_LANGUAGE" \
  --hf_token "${HF_TOKEN:-}"

# 9. Speaker Matching and TXT generation
JSON_OUTPUT="${OUT_DIR}/$(basename "$NORM_WAV" .wav).json"
FINAL_TXT="${OUT_DIR}/${STEM}.txt"

# Double check if matching should run
if [ "$ENABLE_SPEAKER_MATCHING" = "true" ] && [ -d "$SPEAKER_DIR" ]; then
  PROFILE_COUNT=$(find "$SPEAKER_DIR" -maxdepth 1 -name "*.npy" 2>/dev/null | wc -l)

  if [ "$PROFILE_COUNT" -gt 0 ]; then
    echo "Matching: Enabled ($PROFILE_COUNT profiles found)."
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/scripts/match_speakers.py" \
      --json "$JSON_OUTPUT" \
      --audio "$NORM_WAV" \
      --speakers_dir "$SPEAKER_DIR" \
      --threshold "$WHX_SPEAKER_THRESHOLD" \
      --output_txt "$FINAL_TXT" \
      --hf_token "${HF_TOKEN:-}"
  else
    echo "Matching: Enabled, but NO profiles found in $SPEAKER_DIR."
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/scripts/match_speakers.py" \
      --json "$JSON_OUTPUT" \
      --audio "$NORM_WAV" \
      --output_txt "$FINAL_TXT"
  fi
else
  echo "Matching: Disabled."
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/scripts/match_speakers.py" \
    --json "$JSON_OUTPUT" \
    --audio "$NORM_WAV" \
    --output_txt "$FINAL_TXT"
fi

rm -f "$JSON_OUTPUT"
echo "Done! Result: $FINAL_TXT"