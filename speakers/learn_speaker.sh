#!/usr/bin/env bash
set -euo pipefail

# learn_speaker.sh - Create a speaker profile from audio sample
#
# Usage:
#   speakers/learn sample.wav "John Doe"
#   speakers/learn interview.mp3 "Jane Smith"
#
# Creates:
#   - ./speakers/data/{speaker_id}.npy (embedding vector)
#   - ./speakers/data/speakers.json (metadata)
#   - ./samples/{audio_file} (copy of audio sample)

SCRIPT_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# Load config for HF_TOKEN
CONFIG_FILE="$SCRIPT_DIR/config.rc"
if [ -f "$CONFIG_FILE" ]; then
  # shellcheck source=/dev/null
  source "$CONFIG_FILE"
fi

# Usage check
if [ $# -lt 2 ]; then
  echo "Usage: $0 <audio_file> <speaker_name>"
  echo
  echo "Example:"
  echo "  $0 john_sample.wav \"John Doe\""
  echo
  echo "Requirements:"
  echo "  - Audio file: 10-60 seconds of clear speech"
  echo "  - Speaker name: Full name or identifier"
  exit 1
fi

INPUT_AUDIO="$1"
SPEAKER_NAME="$2"

# Validate input file
if [ ! -f "$INPUT_AUDIO" ]; then
  echo "ERROR: Audio file not found: $INPUT_AUDIO"
  exit 1
fi

# Check prerequisites
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERROR: ffmpeg not found in PATH"
  exit 1
fi

if ! command -v ffprobe >/dev/null 2>&1; then
  echo "ERROR: ffprobe not found in PATH"
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "ERROR: Python venv not found at $VENV_DIR"
  echo "Please run ./install.sh first"
  exit 1
fi

# Generate speaker ID (lowercase, spaces to underscores)
SPEAKER_ID="${SPEAKER_NAME,,}"
SPEAKER_ID="${SPEAKER_ID// /_}"
SPEAKER_ID="${SPEAKER_ID//[^a-z0-9_]/}"  # Remove special chars

if [ -z "$SPEAKER_ID" ]; then
  echo "ERROR: Invalid speaker name (resulted in empty ID)"
  exit 1
fi

SPEAKER_DIR="$SCRIPT_DIR/speakers/data"
SAMPLES_DIR="$SCRIPT_DIR/samples"
mkdir -p "$SPEAKER_DIR"
mkdir -p "$SAMPLES_DIR"

# Check duration
echo "Validating audio duration..."
DURATION=$(ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "$INPUT_AUDIO" 2>/dev/null || echo "0")

if (( $(echo "$DURATION < 10" | bc -l 2>/dev/null || echo "0") )); then
  echo "ERROR: Audio too short (${DURATION}s). Need at least 10 seconds of clear speech."
  echo
  echo "Tips:"
  echo "  - Use a recording where the person speaks continuously"
  echo "  - Minimum 10 seconds, recommended 20-30 seconds"
  echo "  - Avoid background noise or music"
  exit 1
fi

if (( $(echo "$DURATION > 60" | bc -l 2>/dev/null || echo "0") )); then
  echo "Note: Audio is ${DURATION}s long. Using first 60 seconds."
  DURATION=60
fi

# Check if profile already exists
if [ -f "$SPEAKER_DIR/${SPEAKER_ID}.npy" ]; then
  echo "WARNING: Speaker profile already exists: $SPEAKER_ID"
  echo -n "Overwrite? [y/N] "
  read -r response
  if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
  fi
fi

# Determine audio file path for metadata
# Convert input to absolute path
INPUT_AUDIO_ABS="$(realpath "$INPUT_AUDIO")"
INPUT_BASENAME="$(basename "$INPUT_AUDIO")"

# Check if audio is already in samples/ directory
SAMPLES_DIR_ABS="$(realpath "$SAMPLES_DIR")"
AUDIO_FILE_FOR_METADATA=""

if [[ "$INPUT_AUDIO_ABS" == "$SAMPLES_DIR_ABS"/* ]]; then
  # Audio is already in samples/ - use relative path
  AUDIO_FILE_FOR_METADATA="samples/$INPUT_BASENAME"
  echo "Using audio from samples/ directory"
else
  # Audio is external - copy to samples/
  DEST_AUDIO="$SAMPLES_DIR/$INPUT_BASENAME"

  # Handle filename collision
  if [ -f "$DEST_AUDIO" ] && [ "$INPUT_AUDIO_ABS" != "$(realpath "$DEST_AUDIO")" ]; then
    # File exists and is different - add timestamp to filename
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    EXT="${INPUT_BASENAME##*.}"
    BASE="${INPUT_BASENAME%.*}"
    INPUT_BASENAME="${BASE}_${TIMESTAMP}.${EXT}"
    DEST_AUDIO="$SAMPLES_DIR/$INPUT_BASENAME"
  fi

  echo "Copying audio to samples/ directory..."
  cp "$INPUT_AUDIO_ABS" "$DEST_AUDIO"
  echo "Copied: $DEST_AUDIO"

  AUDIO_FILE_FOR_METADATA="samples/$INPUT_BASENAME"
fi

# Convert to 16kHz mono WAV (required by pyannote)
TEMP_WAV="/tmp/whx_${SPEAKER_ID}_temp.wav"
trap "rm -f $TEMP_WAV" EXIT

echo "Converting audio to 16kHz mono WAV..."
ffmpeg -hide_banner -loglevel error -y \
  -i "$INPUT_AUDIO" \
  -t 60 \
  -ac 1 \
  -ar 16000 \
  -c:a pcm_s16le \
  "$TEMP_WAV"

# Extract embedding using Python script
echo "Extracting speaker embedding..."
"$VENV_DIR/bin/python" "$SCRIPT_DIR/scripts/extract_speaker_embedding.py" \
  --input "$TEMP_WAV" \
  --output "$SPEAKER_DIR/${SPEAKER_ID}.npy" \
  --speaker_name "$SPEAKER_NAME" \
  --metadata "$SPEAKER_DIR/speakers.json" \
  --hf_token "${HF_TOKEN:-}" \
  --original_audio "$AUDIO_FILE_FOR_METADATA"

# Check if successful
if [ $? -eq 0 ] && [ -f "$SPEAKER_DIR/${SPEAKER_ID}.npy" ]; then
  echo
  echo "✓ Speaker profile created successfully!"
  echo
  echo "  Name:     $SPEAKER_NAME"
  echo "  ID:       $SPEAKER_ID"
  echo "  Profile:  $SPEAKER_DIR/${SPEAKER_ID}.npy"
  echo "  Audio:    $AUDIO_FILE_FOR_METADATA"
  echo "  Duration: ${DURATION}s"
  echo
  echo "Next steps:"
  echo "  1. Enable speaker matching in config.rc:"
  echo "     export WHX_ENABLE_SPEAKER_MATCHING=\"true\""
  echo
  echo "  2. Run transcription:"
  echo "     whx /path/to/media.mp4"
  echo
else
  echo
  echo "✗ Failed to create speaker profile"
  echo "Check error messages above"
  exit 1
fi
