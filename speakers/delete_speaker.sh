#!/usr/bin/env bash
set -euo pipefail

# delete_speaker.sh - Delete a speaker profile
#
# Usage:
#   speakers/delete <speaker_id>
#   speakers/delete john_doe

SCRIPT_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <speaker_id>"
  echo
  echo "List available speakers with: speakers/list"
  exit 1
fi

SPEAKER_ID="$1"

# Use Python utility to delete
"$VENV_DIR/bin/python" -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/scripts')
from utils import delete_speaker, get_speakers_dir

if delete_speaker('$SPEAKER_ID'):
    print(f'✓ Deleted speaker profile: $SPEAKER_ID')
    print(f'  Location: {get_speakers_dir()}')
else:
    print(f'✗ Speaker profile not found: $SPEAKER_ID', file=sys.stderr)
    print(f'', file=sys.stderr)
    print(f'List available speakers with: speakers/list', file=sys.stderr)
    sys.exit(1)
"
