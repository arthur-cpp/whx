#!/usr/bin/env bash
set -euo pipefail

# list_speakers.sh - List all registered speaker profiles
#
# Usage:
#   speakers/list

SCRIPT_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
SPEAKER_DIR="$SCRIPT_DIR/speakers/data"

if [ ! -d "$SPEAKER_DIR" ]; then
  echo "No speaker profiles found."
  echo "Create a profile with: speakers/learn <audio_file> <name>"
  exit 0
fi

# Check if speakers.json exists
METADATA="$SPEAKER_DIR/speakers.json"
if [ ! -f "$METADATA" ]; then
  echo "No speaker metadata found."
  exit 0
fi

# Use Python to pretty-print the list
"$VENV_DIR/bin/python" -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')
from utils import list_speakers

speakers = list_speakers()

if not speakers:
    print('No speaker profiles found.')
    sys.exit(0)

print(f'Registered speakers ({len(speakers)}):')
print()

for s in speakers:
    print(f\"  • {s['name']}\")
    print(f\"    ID:      {s['id']}\")
    print(f\"    Created: {s['created']}\")
    print(f\"    Duration: {s['duration']}s\")
    print(f\"    Model:   {s['model']}\")
    print()
"
